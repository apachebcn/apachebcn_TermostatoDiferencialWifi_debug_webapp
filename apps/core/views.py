import logging
from datetime import datetime, time, timedelta

from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .helper import (
    RESOLUTION_AUTO,
    build_export_dataframe,
    get_default_range,
    get_graph_series,
    normalize_date_input,
    parse_local_date,
    parse_local_datetime,
)
from .models import InputDataHistory, UserProfile

logger = logging.getLogger('django')


def form_login(request):
    if request.user.is_authenticated:
        return redirect('history_data_graph_view')

    error = None
    if request.method == 'POST':
        apikey = (request.POST.get('apikey') or '').strip()
        if apikey:
            profile = UserProfile.objects.filter(apikey=apikey).select_related('user').first()
            # Solo se entra si la apikey corresponde a un usuario con datos.
            if profile and InputDataHistory.objects.filter(user_id=profile.user).exists():
                user = profile.user
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                auth_login(request, user)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
                    return redirect(next_url)
                return redirect('history_data_graph_view')
        error = 'Apikey no válida o sin datos asociados.'

    return render(request, 'form_login.html', {'error': error})


def form_logout(request):
    auth_logout(request)
    return redirect('form_login')


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def insert_input_data_view(request):
    """
    Recepción de datos del ESP32 (igual que la app original: parámetros en la
    URL con la apikey del usuario). Se guardan TODOS los parámetros recibidos
    (excepto la apikey) tal cual, como JSON, en InputDataHistory.data.
    """
    params = request.GET if request.method == 'GET' else request.POST
    apikey = (params.get('apikey') or '').strip()

    if not apikey:
        return HttpResponse(
            'result=error&message=apikey requerida',
            content_type='text/plain',
            status=403,
        )

    profile = UserProfile.objects.filter(apikey=apikey).select_related('user').first()
    if not profile:
        logger.warning('Insert data: apikey inválida')
        return HttpResponse(
            'result=error&message=apikey inválida',
            content_type='text/plain',
            status=403,
        )

    data = {key: value for key, value in params.items() if key != 'apikey'}

    # Solo un registro por usuario y segundo.
    now = timezone.now()
    second_start = now.replace(microsecond=0)
    second_end = second_start + timedelta(seconds=1)
    duplicate = InputDataHistory.objects.filter(
        user_id=profile.user,
        created_at__gte=second_start,
        created_at__lt=second_end,
    ).exists()
    if duplicate:
        return HttpResponse(
            'result=error&message=dato duplicado (ya hay un registro en este segundo)',
            content_type='text/plain',
            status=409,
        )

    try:
        InputDataHistory.objects.create(user_id=profile.user, data=data)
    except IntegrityError:
        # Carrera entre dos peticiones del mismo segundo.
        return HttpResponse(
            'result=error&message=dato duplicado (ya hay un registro en este segundo)',
            content_type='text/plain',
            status=409,
        )

    return HttpResponse(f'result=WEBAPP_OK&apikey={apikey}', content_type='text/plain')


@login_required
def history_data_graph_view(request):
    start_utc, end_utc, start_local, end_local = get_default_range()
    start_local = normalize_date_input(request.GET.get('start_local_date_str')) or start_local
    end_local = normalize_date_input(request.GET.get('end_local_date_str')) or end_local

    context = {
        'start_local_date_str': start_local,
        'end_local_date_str': end_local,
    }
    return render(request, 'pages/graph_history.html', context)


@login_required
def get_nearest_data_day_view(request):
    """Día local con datos más cercano en la dirección indicada (prev / next).

    Si el día inmediatamente anterior/siguiente no tiene datos se devuelve el
    día con datos más cercano en esa dirección.
    """
    target_date = parse_local_date(request.GET.get('date'))
    direction = (request.GET.get('direction') or 'next').strip().lower()
    if not target_date:
        return JsonResponse({'status': 'error', 'error': 'Fecha no válida'})
    if direction not in ('prev', 'next'):
        return JsonResponse({'status': 'error', 'error': 'Dirección no válida'})

    tz = timezone.get_current_timezone()
    day_start = timezone.make_aware(datetime.combine(target_date, time.min), tz)
    day_end = timezone.make_aware(datetime.combine(target_date, time.max), tz)
    queryset = InputDataHistory.objects.filter(user_id=request.user, created_at__isnull=False)

    if direction == 'next':
        adjacent_date = target_date + timedelta(days=1)
        stamp = (
            queryset.filter(created_at__gt=day_end)
            .order_by('created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        empty_message = f'No hay datos posteriores al {target_date:%d/%m/%Y}'
    else:
        adjacent_date = target_date - timedelta(days=1)
        stamp = (
            queryset.filter(created_at__lt=day_start)
            .order_by('-created_at')
            .values_list('created_at', flat=True)
            .first()
        )
        empty_message = f'No hay datos anteriores al {target_date:%d/%m/%Y}'

    if stamp is None:
        return JsonResponse({'status': 'error', 'error': empty_message})

    found_date = timezone.localtime(stamp, tz).date()
    return JsonResponse({
        'status': 'ok',
        'date': found_date.strftime('%d/%m/%Y'),
        'adjacent_date': adjacent_date.strftime('%d/%m/%Y'),
        'has_data_on_adjacent': found_date == adjacent_date,
    })


@login_required
def get_json_data_graph_view(request):
    # Los datos son siempre los del usuario autenticado (no se acepta user_id por GET).
    user_id = request.user.id

    start_utc = parse_local_datetime(request.GET.get('start_local_date_str'))
    end_utc = parse_local_datetime(request.GET.get('end_local_date_str'), end_of_minute=True)
    if not start_utc or not end_utc:
        return JsonResponse({'status': 'error', 'error': 'Fechas no válidas'})
    if start_utc > end_utc:
        return JsonResponse({'status': 'error', 'error': 'La fecha fin no puede ser anterior a la fecha inicio'})

    resolution = (request.GET.get('resolution') or '').strip() or RESOLUTION_AUTO
    payload = get_graph_series(user_id, start_utc, end_utc, resolution)
    return JsonResponse(payload)


@login_required
def data_history_export_view(request):
    # Exportación siempre de los datos del usuario autenticado.
    user_id = request.user.id

    start_utc = parse_local_datetime(request.GET.get('start_local_date_str'))
    end_utc = parse_local_datetime(request.GET.get('end_local_date_str'), end_of_minute=True)
    if not start_utc or not end_utc:
        return HttpResponse('Fechas no válidas', content_type='text/plain', status=400)

    df = build_export_dataframe(user_id, start_utc, end_utc)
    if df is None or df.empty:
        return HttpResponse('No hay datos para el rango seleccionado', content_type='text/plain', status=404)

    filename = f'termostato_debug_{request.user.username}.csv'
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    df.to_csv(response, index=False)
    return response


@login_required
@require_POST
def data_history_delete_range_view(request):
    """Borra los registros del usuario dentro del rango de fechas indicado."""
    start_utc = parse_local_datetime(request.POST.get('start_local_date_str'))
    end_utc = parse_local_datetime(request.POST.get('end_local_date_str'), end_of_minute=True)
    if not start_utc or not end_utc:
        return JsonResponse({'status': 'error', 'error': 'Fechas no válidas'})
    if start_utc > end_utc:
        return JsonResponse({
            'status': 'error',
            'error': 'La fecha fin no puede ser anterior a la fecha inicio',
        })

    queryset = InputDataHistory.objects.filter(
        user_id=request.user,
        created_at__gte=start_utc,
        created_at__lte=end_utc,
    )
    count = queryset.count()
    queryset.delete()
    return JsonResponse({'status': 'ok', 'deleted': count})


@login_required
@require_POST
def data_history_delete_all_view(request):
    """Borra TODO el historial del usuario autenticado (acción irreversible)."""
    queryset = InputDataHistory.objects.filter(user_id=request.user)
    count = queryset.count()
    queryset.delete()
    messages.success(request, f'Se han borrado {count} registros del historial.')
    return redirect('history_data_graph_view')
