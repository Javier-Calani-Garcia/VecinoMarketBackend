from rest_framework import serializers

from .models import MetodoPago


class _MetodoPagoBaseSerializer(serializers.ModelSerializer):
    empresa_nombre = serializers.CharField(source='empresa.razon_social', read_only=True)
    imagen_qr_url = serializers.SerializerMethodField()

    class Meta:
        model = MetodoPago
        fields = [
            'id', 'empresa', 'empresa_nombre', 'tipo', 'nombre',
            'banco', 'numero_cuenta', 'titular',
            'imagen_qr', 'imagen_qr_url',
            'proveedor_pasarela', 'referencia_pasarela',
            'predeterminado', 'creado_en',
        ]
        extra_kwargs = {'imagen_qr': {'write_only': True, 'required': False}}

    def get_imagen_qr_url(self, obj):
        url = obj.imagen_qr_url
        request = self.context.get('request')
        if request and url and url.startswith('/'):
            return request.build_absolute_uri(url)
        return url


class MetodoPagoAdminSerializer(_MetodoPagoBaseSerializer):
    """CU25: el SuperAdmin/Admin puede registrar el método a nombre de
    cualquier empresa (el campo 'empresa' es editable)."""


class MetodoPagoEmpresaSerializer(_MetodoPagoBaseSerializer):
    """CU25: la empresa (dueño o empleado con permiso) gestiona los suyos
    — 'empresa' es de solo lectura, la vista la fuerza a la propia."""

    class Meta(_MetodoPagoBaseSerializer.Meta):
        extra_kwargs = {
            **_MetodoPagoBaseSerializer.Meta.extra_kwargs,
            'empresa': {'read_only': True},
        }
