# start content for invoke
if MODE != "DEV":
	raise Exception(f"ERROR: La variable de entorno MODE indica que está en modo '{MODE}'. Pero este settings pertenece al MODE DEV")

# Lista de administradores del sitio que recibirán notificaciones de errores del servidor.
ADMINS = []
MANAGERS = ADMINS

# Configuración de correo electrónico para desarrollo
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Lista de hosts permitidos para acceder a la aplicación
ALLOWED_HOSTS = [
	'*',
]

# Configuración de CSRF para desarrollo
CSRF_TRUSTED_ORIGINS = []
