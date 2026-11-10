from datetime import datetime, time, timedelta, timezone as dt_timezone

import pandas as pd
from django.utils import timezone

from .models import InputDataHistory


def _get_timezone():
    return timezone.get_current_timezone()


# Formato de fecha usado en los selectores de la vista de gráficos.
DATE_INPUT_FORMAT = '%d/%m/%Y %H:%M'


def format_date_input(dt_local):
    """Devuelve una fecha local en el formato de los selectores (dd/mm/yyyy hh:mm)."""
    return dt_local.strftime(DATE_INPUT_FORMAT)


def normalize_date_input(value_str):
    """Normaliza una fecha al formato dd/mm/yyyy hh:mm (None si no es válida)."""
    value_utc = parse_local_datetime(value_str)
    if not value_utc:
        return None
    return format_date_input(timezone.localtime(value_utc, _get_timezone()))


def parse_local_date(value_str):
    """Interpreta una fecha local sin hora (dd/mm/yyyy o yyyy-mm-dd)."""
    if not value_str:
        return None
    value_str = str(value_str).strip()
    for fmt in ('%d/%m/%Y', '%Y-%m-%d'):
        try:
            return datetime.strptime(value_str, fmt).date()
        except ValueError:
            continue
    return None


def parse_local_datetime(value_str, end_of_minute=False):
    """Interpreta una fecha local y devuelve el equivalente UTC aware.

    Con end_of_minute=True, una hora sin segundos (p.ej. '08:48' del selector
    dd/mm/yyyy hh:mm) se redondea al final del minuto para que el filtro incluya
    todo el minuto seleccionado.
    """
    if not value_str:
        return None
    value_str = str(value_str).strip()
    second_formats = ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S')
    minute_formats = ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M')
    for fmt in second_formats:
        try:
            dt = datetime.strptime(value_str, fmt)
            aware = timezone.make_aware(dt, _get_timezone())
            return aware.astimezone(dt_timezone.utc)
        except ValueError:
            continue
    for fmt in minute_formats:
        try:
            dt = datetime.strptime(value_str, fmt)
            if end_of_minute:
                dt = dt + timedelta(seconds=59)
            aware = timezone.make_aware(dt, _get_timezone())
            return aware.astimezone(dt_timezone.utc)
        except ValueError:
            continue
    return None


def get_default_range():
    """Rango por defecto: desde las 00:00 local de hoy hasta ahora."""
    now_local = timezone.localtime(timezone.now(), _get_timezone())
    start_local = datetime.combine(now_local.date(), time.min)
    start_utc = timezone.make_aware(start_local, _get_timezone()).astimezone(dt_timezone.utc)
    end_utc = timezone.now()
    return (
        start_utc,
        end_utc,
        format_date_input(start_local),
        format_date_input(now_local),
    )


# Resoluciones ofrecidas en la vista de gráficos.
# 'auto'   -> sin agrupar mientras el volumen sea asumible; si no, agrupa.
# 'raw'    -> todos los datos tal cual llegaron (sin agrupar).
RESOLUTION_AUTO = 'auto'
RESOLUTION_RAW = 'raw'

NICE_FREQS = [
    ('5s', 5),
    ('10s', 10),
    ('15s', 15),
    ('30s', 30),
    ('1min', 60),
    ('5min', 300),
    ('15min', 900),
    ('30min', 1800),
    ('1h', 3600),
    ('6h', 21600),
    ('1D', 86400),
    ('1W', 604800),
]
VALID_FREQS = {name for name, _ in NICE_FREQS}

# En modo 'auto' se devuelven todos los datos si no se superan estas filas.
RAW_AUTO_MAX_ROWS = 20000
# En modo 'raw' explícito se permite hasta este número de filas.
RAW_MAX_ROWS = 100000


def _auto_freq(total_seconds, rows):
    """Frecuencia de agrupación para que el número de puntos sea razonable."""
    max_points = 20000
    needed_seconds = total_seconds / max_points
    for name, seconds in NICE_FREQS:
        if seconds >= needed_seconds:
            return name
    return NICE_FREQS[-1][0]


STATE_PREFIXES = ('rel', 'pump', 'rule')
STATE_EXACT = {'errors'}

TRUE_VALUES = {'true', 'on', 'yes', 'si', 'sí', 'high'}
FALSE_VALUES = {'false', 'off', 'no', 'low'}


def _is_state_key(key):
    """Relés, bombas, reglas y errores van a la gráfica de estados."""
    return key in STATE_EXACT or key.startswith(STATE_PREFIXES)


def _convert_boolean_value(value):
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in TRUE_VALUES:
            return 1
        if text in FALSE_VALUES:
            return 0
    return value


def _to_numeric(series):
    """Convierte a numérico aceptando también booleanos como true/false/on/off."""
    return pd.to_numeric(series.map(_convert_boolean_value), errors='coerce')


def _is_step_key(key, numeric_series):
    """Serie discreta (0/1/2) que se dibuja como escalón."""
    if key.endswith('_umbral'):
        return False
    if numeric_series.empty:
        return False
    step_values = {0, 1, 2}
    return all(value in step_values for value in numeric_series.tolist())


def _iter_rows(user_id, start_utc, end_utc):
    return (
        InputDataHistory.objects
        .filter(user_id_id=user_id, created_at__gte=start_utc, created_at__lte=end_utc)
        .order_by('created_at')
        .values('created_at', 'data')
    )


def get_graph_series(user_id, start_utc, end_utc, resolution=RESOLUTION_AUTO):
    records = []
    keys = []
    seen = set()

    for row in _iter_rows(user_id, start_utc, end_utc):
        data = row['data'] or {}
        if not isinstance(data, dict):
            data = {}
        for key in data:
            if key not in seen:
                seen.add(key)
                keys.append(key)
        record = {'created_at': row['created_at']}
        record.update(data)
        records.append(record)

    # Orden alfabético (jsonb no conserva el orden de llegada del ESP32).
    keys = sorted(keys)

    if not records:
        return {
            'status': 'error',
            'error': 'No hay datos para el usuario y rango seleccionados',
        }

    rows_count = len(records)
    total_seconds = (end_utc - start_utc).total_seconds()

    # Decidir resolución efectiva:
    #   'raw'  -> todos los datos sin agrupar
    #   '<freq>' -> agrupado
    if resolution == RESOLUTION_RAW:
        if rows_count > RAW_MAX_ROWS:
            return {
                'status': 'error',
                'error': (
                    f'El rango contiene {rows_count} registros y el máximo para ver '
                    f'todos los datos sin agrupar es {RAW_MAX_ROWS}. '
                    'Reduce las fechas o elige otra resolución.'
                ),
            }
        freq = RESOLUTION_RAW
    elif resolution in VALID_FREQS:
        freq = resolution
    else:
        if rows_count <= RAW_AUTO_MAX_ROWS:
            freq = RESOLUTION_RAW
        else:
            freq = _auto_freq(total_seconds, rows_count)

    df = pd.DataFrame(records)
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df = df.set_index('created_at')
    df = df.sort_index()

    numeric = {key: _to_numeric(df[key]) for key in keys}
    numeric_df = pd.DataFrame(numeric).sort_index()

    temp_keys = [key for key in keys if not _is_state_key(key)]
    state_keys = [key for key in keys if _is_state_key(key)]

    # Solo columnas con algún valor numérico (se descartan 'ip', 'version', ...).
    temp_keys = [key for key in temp_keys if numeric_df[key].notna().any()]
    step_keys = [
        key for key in state_keys
        if key in numeric_df.columns
        and _is_step_key(key, numeric_df[key].dropna())
    ]
    line_keys = [
        key for key in state_keys
        if key in numeric_df.columns
        and key not in step_keys
        and numeric_df[key].notna().any()
    ]

    def _build_points(series, to_int=False):
        points = []
        for ts, value in series.items():
            timestamp_ms = int(ts.timestamp() * 1000)
            if pd.isna(value):
                points.append([timestamp_ms, None])
            elif to_int:
                points.append([timestamp_ms, int(round(float(value)))])
            else:
                points.append([timestamp_ms, round(float(value), 2)])
        return points

    if freq == RESOLUTION_RAW:
        temps_data = numeric_df[temp_keys] if temp_keys else None
        steps_data = numeric_df[step_keys] if step_keys else None
        lines_data = numeric_df[line_keys] if line_keys else None
    else:
        temps_data = numeric_df[temp_keys].resample(freq).mean() if temp_keys else None
        # Los estados se agrupan con max() para no perder ningún "on" dentro del intervalo.
        steps_data = numeric_df[step_keys].resample(freq).max() if step_keys else None
        lines_data = numeric_df[line_keys].resample(freq).mean() if line_keys else None

    temperatures = []
    for key in temp_keys:
        temperatures.append({
            'name': key,
            'object_name': key,
            'data': _build_points(temps_data[key]),
        })

    relays_pumps = []
    for key in state_keys:
        if key in step_keys:
            relays_pumps.append({
                'name': key,
                'object_name': key,
                'step': True,
                'data': _build_points(steps_data[key], to_int=True),
            })
        elif key in line_keys:
            relays_pumps.append({
                'name': key,
                'object_name': key,
                'step': False,
                'data': _build_points(lines_data[key]),
            })

    points_count = sum(len(series['data']) for series in temperatures)
    points_count += sum(len(series['data']) for series in relays_pumps)

    return {
        'status': 'ok',
        'info': {
            'user_id': user_id,
            'start_utc': start_utc.isoformat(),
            'end_utc': end_utc.isoformat(),
            'resample': freq,
            'rows': rows_count,
            'points': points_count,
            'temperatures_count': len(temperatures),
            'relays_pumps_count': len(relays_pumps),
        },
        'data': {
            'temperatures': temperatures,
            'relays_pumps': relays_pumps,
        },
    }


def build_export_dataframe(user_id, start_utc, end_utc):
    records = []
    keys = []
    seen = set()

    for row in _iter_rows(user_id, start_utc, end_utc):
        data = row['data'] or {}
        if not isinstance(data, dict):
            data = {}
        for key in data:
            if key not in seen:
                seen.add(key)
                keys.append(key)
        record = {'created_at': row['created_at']}
        record.update(data)
        records.append(record)

    # Orden alfabético (jsonb no conserva el orden de llegada del ESP32).
    keys = sorted(keys)

    if not records:
        return None

    df = pd.DataFrame(records)
    df['created_at'] = pd.to_datetime(df['created_at'], utc=True)
    df = df.sort_values('created_at')
    df['created_at'] = (
        df['created_at']
        .dt.tz_convert(_get_timezone())
        .dt.strftime('%Y-%m-%d %H:%M:%S')
    )
    df.insert(0, 'user_id', user_id)
    # Reordenar: user_id, created_at, ...campos tal como los envía el ESP32.
    ordered = ['user_id', 'created_at'] + keys
    return df[[col for col in ordered if col in df.columns]]
