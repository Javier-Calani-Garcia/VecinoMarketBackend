from django.db.models import Sum
from django.db.models.functions import Coalesce
from rest_framework import generics
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny

from .models import Categoria, Producto
from .serializers import CategoriaSerializer, ProductoSerializer


class CatalogoPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = 'page_size'
    max_page_size = 100


def _productos_queryset():
    return (
        Producto.objects.filter(activo=True, estado=Producto.Estado.ACTIVO)
        .select_related('categoria', 'empresa')
        .prefetch_related('imagenes')
        .annotate(stock=Coalesce(Sum('inventarios__cantidad_disponible'), 0))
    )


class ListaCategoriasView(generics.ListAPIView):
    """Catálogo público de categorías (no dependen de una empresa en particular)."""

    permission_classes = [AllowAny]
    serializer_class = CategoriaSerializer
    queryset = Categoria.objects.filter(activo=True, categoria_padre__isnull=True).order_by('nombre')


class ListaProductosView(generics.ListAPIView):
    """Catálogo público de productos: soporta ?categoria=<id>, ?empresa=<id> y ?q=<texto>."""

    permission_classes = [AllowAny]
    serializer_class = ProductoSerializer
    pagination_class = CatalogoPagination
    filterset_fields = ['categoria', 'empresa']

    def get_queryset(self):
        qs = _productos_queryset().order_by('-creado_en')
        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q)
        return qs


class DetalleProductoView(generics.RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductoSerializer
    queryset = _productos_queryset()
