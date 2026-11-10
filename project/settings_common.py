"""
	Este fichero es parte de la construcción automática del settings.py
	Se combina éste (settings_common.py) con uno de los ficheros de
	settings-files/ (settings-local-dev.py, settings-local-prod.py,
	settings-server-dev.py o settings-server-prod.py) según el perfil
	seleccionado desde el comando 'invoke' en la raíz del docker.

	Las variables que se leen del entorno (get_env_value) deben estar
	definidas en el entorno del contenedor (fichero .env generado por invoke
	o el compose).

	Para regenerar settings.py desde la raíz del docker:
	$ invoke dev     (o invoke prod)
	$ invoke config  (o invoke up)
"""

# start content for invoke
import os

print_os_vars = False


def _get_env_bool_value(name):
	if name not in os.environ:
		raise Exception(f"{name} not in environment")
	value = os.getenv(name)
	if value is None:
		return False
	if value is False:
		return False
	if value is True:
		return True
	if str(value).lower() == 'true':
		return True
	if str(value).lower() == 'false':
		return False
	return False


def _get_env_int_value(name, default=""):
	if name not in os.environ:
		raise Exception(f"{name} not in environment")
	value = os.getenv(name, default)
	try:
		return int(value)
	except (ValueError, TypeError):
		return default


def get_env_value(name, type_var='char', default=""):
	if name not in os.environ:
		raise Exception(f"{name} not in environment")
	if type_var == 'char':
		value = os.getenv(name, default)
		if print_os_vars:
			print(f"{name} = {value}")
		return value
	if type_var == 'int':
		value = _get_env_int_value(name, default)
		if print_os_vars:
			print(f"{name} = {value}")
		return value
	if type_var == 'bool':
		value = _get_env_bool_value(name)
		if print_os_vars:
			print(f"{name} = {value}")
		return value
	return value


MODE = get_env_value('MODE')
DEBUG = get_env_value('DJANGO_DEBUG', 'bool', False)
SECRET_KEY = get_env_value('DJANGO_SECRET_KEY')

if not MODE or MODE not in ["DEV", "PROD"]:
	raise Exception(f"ERROR: La variable de entorno MODE no está definida correctamente. Valor = '{MODE}'")


INSTALLED_APPS = [
	'django.contrib.admin',
	'django.contrib.auth',
	'django.contrib.contenttypes',
	'django.contrib.sessions',
	'django.contrib.messages',
	'django.contrib.staticfiles',
	'django.contrib.humanize',
	'django_extensions',
	'apps.core',
]

MIDDLEWARE = [
	'django.middleware.security.SecurityMiddleware',
	'django.contrib.sessions.middleware.SessionMiddleware',
	'django.middleware.common.CommonMiddleware',
	'django.middleware.csrf.CsrfViewMiddleware',
	'django.contrib.auth.middleware.AuthenticationMiddleware',
	'django.contrib.messages.middleware.MessageMiddleware',
	'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'project.urls'

TEMPLATES = [
	{
		'BACKEND': 'django.template.backends.django.DjangoTemplates',
		'DIRS': [os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')],
		'APP_DIRS': True,
		'OPTIONS': {
			'context_processors': [
				'django.template.context_processors.debug',
				'django.template.context_processors.request',
				'django.contrib.auth.context_processors.auth',
				'django.contrib.messages.context_processors.messages',
			],
		},
	},
]

WSGI_APPLICATION = 'project.wsgi.application'

DATABASES = {
	'default': {
		'ENGINE': get_env_value('DB_ENGINE'),
		'NAME': get_env_value('DB_NAME'),
		'USER': get_env_value('DB_USER'),
		'PASSWORD': get_env_value('DB_PASSWORD'),
		'HOST': get_env_value('DB_HOST'),
		'PORT': get_env_value('DB_PORT'),
	}
}

AUTH_PASSWORD_VALIDATORS = []

LANGUAGE_CODE = 'es'
TIME_ZONE = 'Europe/Madrid'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = '/srv/static'
STATICFILES_DIRS = (
	os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'static'),
)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'assets', 'media')

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Acceso: login propio por apikey (ver apps/core/views.py)
LOGIN_URL = '/form_login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/form_login/'
