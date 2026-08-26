from rest_framework import serializers

from apps.usuarios.models import Empresa

from .models import Categoria, Producto, ProductoImagen


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre', 'descripcion', 'icono', 'categoria_padre']


class EmpresaResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = ['id', 'razon_social', 'slug', 'logo_url', 'ciudad', 'departamento']


class ProductoImagenSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductoImagen
        fields = ['id', 'url', 'orden']


class ProductoSerializer(serializers.ModelSerializer):
    empresa = EmpresaResumenSerializer(read_only=True)
    categoria = CategoriaSerializer(read_only=True)
    imagenes = ProductoImagenSerializer(many=True, read_only=True)
    # Anotado en el queryset de la vista (suma de InventarioSucursal por producto).
    stock = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'descripcion', 'sku', 'precio', 'precio_descuento',
            'estado', 'categoria', 'empresa', 'imagenes', 'stock', 'creado_en',
        ]
