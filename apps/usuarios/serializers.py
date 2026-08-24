from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Empresa, Usuario


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['empresa_id'] = user.empresa_id
        token['nombre'] = user.nombre
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        if self.user.empresa_id and not self.user.empresa.suscripcion_activa:
            raise serializers.ValidationError(
                'La empresa no tiene una suscripción activa.'
            )
        return data


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ['id', 'nombre', 'rubro', 'slug', 'descripcion', 'suscripcion_activa']
        read_only_fields = ['id', 'suscripcion_activa']


class CrearEmpresaConAdminSerializer(serializers.Serializer):
    """El superadmin crea la empresa y su usuario admin en una sola operación."""

    nombre = serializers.CharField(max_length=150)
    rubro = serializers.CharField(max_length=100)
    slug = serializers.SlugField()
    descripcion = serializers.CharField(required=False, allow_blank=True)

    admin_email = serializers.EmailField()
    admin_nombre = serializers.CharField(max_length=150)
    admin_password = serializers.CharField(write_only=True, min_length=8)

    def validate_slug(self, value):
        if Empresa.objects.filter(slug=value).exists():
            raise serializers.ValidationError('Ya existe una empresa con ese slug.')
        return value

    def validate_admin_email(self, value):
        if Usuario.objects.filter(email=value).exists():
            raise serializers.ValidationError('Ya existe un usuario con ese email.')
        return value

    def create(self, validated_data):
        superadmin = self.context['request'].user

        empresa = Empresa.objects.create(
            nombre=validated_data['nombre'],
            rubro=validated_data['rubro'],
            slug=validated_data['slug'],
            descripcion=validated_data.get('descripcion', ''),
            creada_por=superadmin,
        )

        admin = Usuario.objects.create_user(
            email=validated_data['admin_email'],
            password=validated_data['admin_password'],
            nombre=validated_data['admin_nombre'],
            rol=Usuario.Rol.ADMIN_EMPRESA,
            empresa=empresa,
            creado_por=superadmin,
        )

        return {'empresa': empresa, 'admin': admin}


class CrearEmpleadoSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'password']
        read_only_fields = ['id']

    def create(self, validated_data):
        admin = self.context['request'].user
        password = validated_data.pop('password')
        return Usuario.objects.create_user(
            password=password,
            rol=Usuario.Rol.EMPLEADO,
            empresa=admin.empresa,   # nunca desde el body: siempre el tenant del admin logueado
            creado_por=admin,
            **validated_data,
        )


class RegistroClienteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'password']
        read_only_fields = ['id']

    def create(self, validated_data):
        password = validated_data.pop('password')
        return Usuario.objects.create_user(
            password=password,
            rol=Usuario.Rol.CLIENTE,
            empresa=None,
            **validated_data,
        )


class UsuarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Usuario
        fields = ['id', 'email', 'nombre', 'rol', 'empresa', 'is_active', 'creado_en']
        read_only_fields = fields
