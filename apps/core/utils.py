import requests
from django.conf import settings


def get_client_ip(request):
    """Obtiene la IP real del cliente, considerando proxies/load balancers."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class RecaptchaError(Exception):
    pass


def verificar_recaptcha(token, request=None):
    """Valida un token de reCAPTCHA v2 contra la API de Google.

    Si no hay clave secreta configurada (entorno de desarrollo sin claves),
    no bloquea la operación. reCAPTCHA v2 es una tecnología de navegador (el
    checkbox no existe como tal fuera de una página web); la app móvil no
    puede resolverlo, así que manda un secreto propio de la app en un header
    en su lugar, que la identifica como cliente de confianza sin exponer la
    verificación a cualquiera que llame al endpoint directamente.
    """
    if not settings.RECAPTCHA_SECRET_KEY:
        return
    if request is not None and settings.MOBILE_APP_SECRET:
        if request.headers.get('X-Mobile-App-Secret') == settings.MOBILE_APP_SECRET:
            return
    if not token:
        raise RecaptchaError('Completa el reCAPTCHA.')
    respuesta = requests.post(
        'https://www.google.com/recaptcha/api/siteverify',
        data={'secret': settings.RECAPTCHA_SECRET_KEY, 'response': token},
        timeout=5,
    )
    if not respuesta.json().get('success'):
        raise RecaptchaError('No se pudo verificar que no eres un robot.')
