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


def verificar_recaptcha(token):
    """Valida un token de reCAPTCHA v2 contra la API de Google.

    Si no hay clave secreta configurada (entorno de desarrollo sin claves),
    no bloquea la operación.
    """
    if not settings.RECAPTCHA_SECRET_KEY:
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
