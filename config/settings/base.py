import platform
from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY', default='django-insecure-cambia-esta-clave')
DEBUG = env.bool('DEBUG', default=False)
ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost', '127.0.0.1'])

# GeoDjango (PostGIS) necesita ubicar las DLLs de GDAL/GEOS en Windows;
# en Linux/Mac las encuentra solo en el path de librerías del sistema.
if platform.system() == 'Windows':
    _PG_BIN = env('PG_BIN_PATH', default=r'C:\Program Files\PostgreSQL\16\bin')
    GDAL_LIBRARY_PATH = env('GDAL_LIBRARY_PATH', default=rf'{_PG_BIN}\libgdal-35.dll')
    GEOS_LIBRARY_PATH = env('GEOS_LIBRARY_PATH', default=rf'{_PG_BIN}\libgeos_c.dll')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',

    'rest_framework',
    'corsheaders',
    'rest_framework_simplejwt.token_blacklist',

    'apps.core',
    'apps.usuarios',
    'apps.catalogo',
    'apps.inventario',
    'apps.pedidos',
    'apps.comunicacion',
    'apps.promociones',
    'apps.reportes',
    'apps.auditoria',
    'apps.notificaciones',
    'apps.suscripciones',
    'apps.facturacion',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.TenantContextMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

DATABASES = {
    'default': env.db(
        'DATABASE_URL',
        default='postgres://vecinomarket:password@localhost:5432/vecinomarket',
    )
}
DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'

AUTH_USER_MODEL = 'usuarios.Usuario'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-bo'
TIME_ZONE = 'America/La_Paz'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework / JWT
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
}

# ---------------------------------------------------------------------------
# CORS (ajustar dominios reales del frontend web/móvil en prod.py)
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env.bool('CORS_ALLOW_ALL_ORIGINS', default=True)

# ---------------------------------------------------------------------------
# Email (recuperación de contraseña, CU/T010). Vía Gmail SMTP con contraseña
# de aplicación. En un entorno sin EMAIL_HOST_USER configurado, cae al
# backend de consola (imprime el correo en la terminal en vez de enviarlo).
# ---------------------------------------------------------------------------
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = env('EMAIL_HOST', default='smtp.gmail.com')
    EMAIL_PORT = env.int('EMAIL_PORT', default=587)
    EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='VecinoMarket <no-reply@vecinomarket.bo>')

# URL del frontend, para armar los links que van en los correos (reset de
# contraseña, etc). En prod se sobreescribe con la URL real desplegada.
FRONTEND_URL = env('FRONTEND_URL', default='http://localhost:5173')

# ---------------------------------------------------------------------------
# Login con Google (Google Identity Services). El Client ID no es secreto
# (también vive en el frontend), así que solo hace falta esta variable acá
# para verificar la firma del ID token que manda el navegador.
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID', default='')

# ---------------------------------------------------------------------------
# reCAPTCHA v2 ("no soy un robot") para login y registro. La clave secreta
# se usa para verificar el token contra la API de Google (ver apps.core.utils).
# ---------------------------------------------------------------------------
RECAPTCHA_SECRET_KEY = env('RECAPTCHA_SECRET_KEY', default='')

# Secreto compartido para que la app móvil (Flutter) se identifique como
# cliente propio y salte el reCAPTCHA en login/registro: reCAPTCHA v2 es un
# widget de navegador, no existe un equivalente nativo para resolverlo desde
# la app. No reemplaza al reCAPTCHA en la web (que sigue exigiéndose igual);
# solo evita bloquear al único otro cliente de confianza que tenemos.
MOBILE_APP_SECRET = env('MOBILE_APP_SECRET', default='')
