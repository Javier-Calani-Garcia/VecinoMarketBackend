"""CU01: creación de la cuenta de empresa (usuario + Empresa + Suscripcion),
compartida por los 3 caminos que la disparan — solicitud con plan Prueba
(automática), solicitud con plan Básico/Premium (tras pagar en PayPal) y
alta directa del SuperAdmin. La empresa siempre es una cuenta nueva y
separada de la del comprador que hizo la solicitud (si la hubo)."""
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from apps.facturacion.models import Factura
from apps.suscripciones.models import Suscripcion

from .models import Empresa, Usuario

_ALFABETO_PASSWORD = 'abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789'


def generar_correo_empresa(email_comprador):
    """juan@gmail.com -> juan+empresa@gmail.com. Si ya existe un Usuario con
    ese alias (poco probable, pero el comprador podría solicitar más de una
    empresa), agrega un sufijo numérico hasta encontrar uno libre."""
    local, _, dominio = email_comprador.partition('@')
    candidato = f'{local}+empresa@{dominio}'
    sufijo = 2
    while Usuario.objects.filter(email=candidato).exists():
        candidato = f'{local}+empresa{sufijo}@{dominio}'
        sufijo += 1
    return candidato


def _generar_slug_empresa(razon_social):
    base = slugify(razon_social)[:70] or 'empresa'
    slug = base
    sufijo = 2
    while Empresa.objects.filter(slug=slug).exists():
        slug = f'{base}-{sufijo}'
        sufijo += 1
    return slug


def crear_cuenta_empresa(razon_social, nit, correo_empresa, plan, documento_url='', codigo_referido='', solicitud=None):
    """Crea la cuenta de empresa completa y le manda las credenciales por
    correo. Devuelve (usuario, empresa, suscripcion)."""
    password = get_random_string(12, allowed_chars=_ALFABETO_PASSWORD)
    usuario = Usuario.objects.create_user(
        email=correo_empresa, password=password, nombre=razon_social, rol=Usuario.Rol.EMPRESA,
    )

    referente = None
    if codigo_referido:
        referente = Empresa.objects.filter(slug=codigo_referido).first()

    empresa = Empresa.objects.create(
        usuario_dueno=usuario,
        solicitud=solicitud,
        razon_social=razon_social,
        nit=nit,
        slug=_generar_slug_empresa(razon_social),
        plan=plan,
        referida_por=referente,
    )

    # CU01: "1 mes/año desde la FECHA Y HORA de adquisición" — fecha_inicio/
    # fecha_vencimiento son datetime exactos, no solo el día.
    ahora = timezone.now()
    vencimiento = ahora + timedelta(days=plan.duracion_dias)
    suscripcion = Suscripcion.objects.create(
        empresa=empresa, plan=plan, fecha_inicio=ahora, fecha_vencimiento=vencimiento,
        estado=Suscripcion.Estado.ACTIVA,
    )

    if plan.precio_mensual > 0:
        Factura.objects.create(
            empresa=empresa, suscripcion=suscripcion, tipo=Factura.Tipo.SUSCRIPCION,
            monto=plan.precio_mensual, periodo_desde=ahora.date(), periodo_hasta=vencimiento.date(),
            estado_pago=Factura.EstadoPago.PAGADA, fecha_pago=ahora,
        )

    send_mail(
        'Tu cuenta de empresa en VecinoMarket',
        (
            f'Hola,\n\n'
            f'Tu cuenta de empresa "{razon_social}" ya está activa con el plan {plan.nombre}.\n\n'
            'Estas son tus credenciales de acceso:\n'
            f'  Correo: {correo_empresa}\n'
            f'  Contraseña: {password}\n\n'
            f'Ingresa aquí: {settings.FRONTEND_URL}/login\n\n'
            'Te recomendamos cambiar la contraseña luego de tu primer ingreso.'
        ),
        settings.DEFAULT_FROM_EMAIL,
        [correo_empresa],
        fail_silently=True,
    )

    return usuario, empresa, suscripcion
