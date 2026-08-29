from rest_framework import serializers

from .models import Valoracion


class ValoracionSerializer(serializers.ModelSerializer):
    """CU04: 'pedido' y 'empresa' son de solo lectura — la reseña nace
    ligada al pedido entregado que el comprador está calificando, la vista
    los deriva y los fuerza (ver ListaCrearMisValoracionesView)."""

    comprador_nombre = serializers.CharField(source='comprador.usuario.nombre', read_only=True)
    empresa_nombre = serializers.CharField(source='empresa.razon_social', read_only=True)
    numero_pedido = serializers.CharField(source='pedido.numero_pedido', read_only=True)

    class Meta:
        model = Valoracion
        fields = [
            'id', 'pedido', 'numero_pedido', 'comprador', 'comprador_nombre',
            'empresa', 'empresa_nombre', 'calificacion', 'comentario', 'creado_en',
        ]
        extra_kwargs = {
            'pedido': {'read_only': True},
            'empresa': {'read_only': True},
            'comprador': {'read_only': True},
        }
