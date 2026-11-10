# start content for invoke
if MODE != "PROD":
	raise Exception(f"ERROR: La variable de entorno MODE indica que está en modo '{MODE}'. Pero este settings pertenece al MODE PROD")

# Lista de administradores del sitio que recibirán notificaciones de errores del servidor.
ADMINS = []
MANAGERS = ADMINS

# Configuración de correo electrónico para producción
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

# Lista de hosts permitidos para acceder a la aplicación
ALLOWED_HOSTS = [
	'127.0.0.1',  # Para que no de problemas con el servidor en el VPS y su nginx
	'debug.app.termostatodiferencial.com',
]

# Configuración de CSRF para producción
CSRF_TRUSTED_ORIGINS = [
	'https://debug.app.termostatodiferencial.com',
]
