from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.core.utils import RecaptchaError, verificar_recaptcha

from .models import Comprador, Empleado, Empresa, Permiso, RolBase, SolicitudEmpresa, Usuario


class LoginSerializer(TokenObtainPairSerializer):
    recaptcha_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        empresa = user.get_empresa()
        token['rol'] = user.rol
        token['empresa_id'] = empresa.id if empresa else None
        token['nombre'] = user.nombre
        return token

    def validate(self, attrs):
        token = attrs.pop('recaptcha_token', '')
        try:
            verificar_recaptcha(token)
        except RecaptchaError as error:
            raise serializers.ValidationError({'recaptcha_token': str(error)})

        data = super().validate(attrs)
        if self.user.estado != Usuario.Estado.ACTIVO:
            raise serializers.ValidationError('El usuario no está activo.')
        return data


class SolicitudEmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudEmpresa
        fields = ['id', 'razon_social', 'nit', 'documento_url', 'estado', 'motivo_rechazo', 'creado_en']
        read_only_fields = ['id', 'estado', 'motivo_rechazo', 'creado_en']

    def create(self, validated_data):
        usuario = self.context['request'].user
        return SolicitudEmpresa.objects.create(usuario_solicitante=usuario, **validated_data)


class AprobarSolicitudSerializer(serializers.Serializer):
    slug = serializers.SlugField()

    def validate_slug(self, value):
        if Empresa.objects.filter(slug=value).exists():
            raise serializers.ValidationError('Ya existe una empresa con ese slug.')
        return value

    def save(self):
        solicitud = self.context['solicitud']
        admin = self.context['request'].user

        empresa = Empresa.objects.create(
            usuario_dueno=solicitud.usuario_solicitante,
            solicitud=solicitud,
            razon_social=solicitud.razon_social,
            nit=solicitud.nit,
            slug=self.validated_data['slug'],
        )

        solicitud.usuario_solicitante.rol = Usuario.Rol.EMPRESA
        solicitud.usuario_solicitante.save(update_fields=['rol'])

        solicitud.estado = SolicitudEmpresa.Estado.APROBADA
        solicitud.revisado_por_admin = admin
        solicitud.fecha_revision = timezone.now()
        solicitud.save(update_fields=['estado', 'revisado_por_admin', 'fecha_revision'])

        return empresa


class RechazarSolicitudSerializer(serializers.Serializer):
    motivo_rechazo = serializers.CharField(max_length=255)

    def save(self):
        solicitud = self.context['solicitud']
        admin = self.context['request'].user
        solicitud.estado = SolicitudEmpresa.Estado.RECHAZADA
        solicitud.revisado_por_admin = admin
        solicitud.motivo_rechazo = self.validated_data['motivo_rechazo']
        solicitud.fecha_revision = timezone.now()
        solicitud.save(update_fields=['estado', 'revisado_por_admin', 'motivo_rechazo', 'fecha_revision'])
        return solicitud


class CrearEmpleadoSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    cargo = serializers.CharField(max_length=60, required=False, allow_blank=True)

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese email.')
        return value

    def create(self, validated_data):
        admin = self.context['request'].user
        empresa = admin.get_empresa()
        password = validated_data.pop('password')
        cargo = validated_data.pop('cargo', '')

        usuario = Usuario.objects.create_user(
            password=password,
            rol=Usuario.Rol.EMPLEADO,
            **validated_data,
        )
        return Empleado.objects.create(usuario=usuario, empresa=empresa, cargo=cargo)


class RegistroCompradorSerializer(serializers.Serializer):
    email = serializers.EmailField()
    nombre = serializers.CharField(max_length=100)
    apellido = serializers.CharField(max_length=100, required=False, allow_blank=True)
    telefono = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8)
    recaptcha_token = serializers.CharField(write_only=True, required=False, allow_blank=True)

    def validate_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese email.')
        return value

    def validate(self, attrs):
        token = attrs.pop('recaptcha_token', '')
        try:
            verificar_recaptcha(token)
        except RecaptchaError as error:
            raise serializers.ValidationError({'recaptcha_token': str(error)})
        return attrs

    def create(self, validated_data):
        password = validated_data.pop('password')
        usuario = Usuario.objects.create_user(
            password=password,
            rol=Usuario.Rol.COMPRADOR,
            **validated_data,
        )
        Comprador.objects.create(usuario=usuario)
        return usuario


class UsuarioSerializer(serializers.ModelSerializer):
    empresa_id = serializers.SerializerMethodField()

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'apellido', 'telefono', 'rol', 'estado', 'empresa_id', 'fecha_registro']
        read_only_fields = fields

    def get_empresa_id(self, obj):
        empresa = obj.get_empresa()
        return empresa.id if empresa else None


class ActualizarPerfilSerializer(serializers.ModelSerializer):
    """T013 (RF07): el usuario edita sus propios datos (no el rol ni el email)."""

    class Meta:
        model = Usuario
        fields = ['nombre', 'apellido', 'telefono']


class CambiarPasswordSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(write_only=True, min_length=8)

    def validate_password_actual(self, value):
        usuario = self.context['request'].user
        if not usuario.check_password(value):
            raise serializers.ValidationError('La contraseña actual no es correcta.')
        return value

    def save(self):
        usuario = self.context['request'].user
        usuario.set_password(self.validated_data['password_nueva'])
        usuario.save(update_fields=['password'])
        return usuario


class SolicitarResetPasswordSerializer(serializers.Serializer):
    """T010 (RF03): envía el link de recuperación por correo si el email existe.

    Siempre reporta éxito (aunque el email no exista) para no revelar qué
    correos están registrados en la plataforma.
    """

    email = serializers.EmailField()

    def save(self):
        usuario = Usuario.objects.filter(email=self.validated_data['email']).first()
        if usuario is None:
            return None

        uid = urlsafe_base64_encode(force_bytes(usuario.pk))
        token = default_token_generator.make_token(usuario)
        link = f'{settings.FRONTEND_URL}/restablecer-password?uid={uid}&token={token}'

        send_mail(
            'Recupera tu contraseña — VecinoMarket',
            (
                f'Hola {usuario.nombre},\n\n'
                'Recibimos una solicitud para restablecer tu contraseña en VecinoMarket. '
                'Si fuiste tú, entra al siguiente link para elegir una nueva:\n\n'
                f'{link}\n\n'
                'Si no fuiste tú, puedes ignorar este correo — tu contraseña actual sigue siendo válida.'
            ),
            settings.DEFAULT_FROM_EMAIL,
            [usuario.email],
            fail_silently=True,
        )
        return usuario


class ConfirmarResetPasswordSerializer(serializers.Serializer):
    """T010 (RF03): valida el link (uid + token) y guarda la nueva contraseña."""

    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, attrs):
        try:
            pk = urlsafe_base64_decode(attrs['uid']).decode()
            usuario = Usuario.objects.get(pk=pk)
        except (Usuario.DoesNotExist, ValueError, TypeError, OverflowError):
            raise serializers.ValidationError('El link no es válido.')

        if not default_token_generator.check_token(usuario, attrs['token']):
            raise serializers.ValidationError('El link no es válido o ya expiró. Solicita uno nuevo.')

        attrs['usuario'] = usuario
        return attrs

    def save(self):
        usuario = self.validated_data['usuario']
        usuario.set_password(self.validated_data['password'])
        usuario.save(update_fields=['password'])
        return usuario


class EmpresaAdminSerializer(serializers.ModelSerializer):
    """T009 (RF01/RF02): listado de empresas para el ADMIN de la plataforma."""

    dueno_email = serializers.EmailField(source='usuario_dueno.email', read_only=True)
    dueno_nombre = serializers.CharField(source='usuario_dueno.nombre', read_only=True)

    class Meta:
        model = Empresa
        fields = [
            'id', 'razon_social', 'nit', 'slug', 'ciudad', 'departamento',
            'estado', 'dueno_email', 'dueno_nombre', 'creado_en',
        ]
        read_only_fields = fields


class PermisoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permiso
        fields = ['id', 'codigo', 'descripcion']
        read_only_fields = fields


class RolBaseSerializer(serializers.ModelSerializer):
    """T054/T055 (RF53/RF54): roles administrativos globales y sus permisos base."""

    permisos = serializers.SerializerMethodField()

    class Meta:
        model = RolBase
        fields = ['id', 'nombre', 'permisos']
        read_only_fields = ['id', 'permisos']

    def get_permisos(self, obj):
        return PermisoSerializer([rp.permiso for rp in obj.permisos.select_related('permiso')], many=True).data


class GoogleAuthSerializer(serializers.Serializer):
    """Login/registro con Google Identity Services: verifica el ID token que
    manda el navegador y, si es la primera vez, crea la cuenta de comprador
    automáticamente (mismo email = misma cuenta, sin importar cómo se creó)."""

    credential = serializers.CharField(write_only=True)

    def validate_credential(self, value):
        try:
            payload = google_id_token.verify_oauth2_token(
                value, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except ValueError:
            raise serializers.ValidationError('El token de Google no es válido o expiró.')

        if not payload.get('email_verified'):
            raise serializers.ValidationError('Tu cuenta de Google no tiene el email verificado.')

        return payload

    def save(self):
        payload = self.validated_data['credential']
        email = payload['email']
        usuario = Usuario.objects.filter(email=email).first()
        creado = False

        if usuario is None:
            usuario = Usuario.objects.create_user(
                email=email,
                password=None,  # cuenta sin contraseña: siempre ingresa por Google
                nombre=payload.get('given_name') or payload.get('name') or email.split('@')[0],
                apellido=payload.get('family_name', ''),
                rol=Usuario.Rol.COMPRADOR,
            )
            Comprador.objects.create(usuario=usuario)
            creado = True

        return usuario, creado
