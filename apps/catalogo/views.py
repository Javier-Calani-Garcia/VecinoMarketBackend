from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.permissions import EsAdmin

from rest_framework.parsers import FormParser, JSONParser, MultiPartParser

from .models import Categoria, Producto, ProductoImagen
from .serializers import (
    CategoriaAdminSerializer,
    CategoriaSerializer,
    ProductoAdminSerializer,
    ProductoImagenSerializer,
    ProductoSerializer,
)


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


def _log(request, accion, entidad_id, detalle=None, entidad_afectada='categoria'):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada=entidad_afectada,
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaCrearCategoriaAdminView(generics.ListCreateAPIView):
    """CU06: el personal de la plataforma ve y crea categorías (incluye
    inactivas, a diferencia del catálogo público)."""

    permission_classes = [EsAdmin]
    serializer_class = CategoriaAdminSerializer
    pagination_class = None
    queryset = Categoria.objects.all().order_by('nombre')

    def perform_create(self, serializer):
        categoria = serializer.save()
        _log(self.request, 'CREAR_CATEGORIA', categoria.id, {'nombre': categoria.nombre})


class EditarEliminarCategoriaAdminView(APIView):
    """CU06: edita o elimina una categoría. Los productos que la tenían
    quedan sin categoría (on_delete=SET_NULL), no se borran."""

    permission_classes = [EsAdmin]

    def patch(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, id=categoria_id)
        serializer = CategoriaAdminSerializer(categoria, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_CATEGORIA', categoria.id, {'nombre': categoria.nombre})
        return Response(serializer.data)

    def delete(self, request, categoria_id):
        categoria = get_object_or_404(Categoria, id=categoria_id)
        nombre = categoria.nombre
        categoria.delete()
        _log(request, 'ELIMINAR_CATEGORIA', categoria_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductosPorCategoriaAdminView(generics.ListAPIView):
    """CU06: qué productos (de cualquier empresa, cualquier estado) hay
    dentro de una categoría."""

    permission_classes = [EsAdmin]
    serializer_class = ProductoSerializer
    pagination_class = CatalogoPagination

    def get_queryset(self):
        return (
            Producto.objects.filter(categoria_id=self.kwargs['categoria_id'])
            .select_related('categoria', 'empresa')
            .prefetch_related('imagenes')
            .annotate(stock=Coalesce(Sum('inventarios__cantidad_disponible'), 0))
            .order_by('-creado_en')
        )


def _productos_admin_queryset():
    return (
        Producto.objects.select_related('categoria', 'empresa')
        .prefetch_related('imagenes')
        .annotate(stock=Coalesce(Sum('inventarios__cantidad_disponible'), 0))
    )


class ListaCrearProductoAdminView(generics.ListCreateAPIView):
    """CU07: el personal de la plataforma ve TODOS los productos (de
    cualquier empresa, cualquier estado) y puede registrar uno nuevo a
    nombre de cualquier empresa."""

    permission_classes = [EsAdmin]
    serializer_class = ProductoAdminSerializer
    pagination_class = CatalogoPagination

    def get_queryset(self):
        qs = _productos_admin_queryset().order_by('-creado_en')

        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)

        categoria_id = self.request.query_params.get('categoria')
        if categoria_id:
            qs = qs.filter(categoria_id=categoria_id)

        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)

        q = self.request.query_params.get('q')
        if q:
            qs = qs.filter(nombre__icontains=q)

        return qs

    def perform_create(self, serializer):
        producto = serializer.save()
        _log(self.request, 'CREAR_PRODUCTO', producto.id, {'nombre': producto.nombre}, entidad_afectada='producto')


class EditarEliminarProductoAdminView(APIView):
    """CU07: edita o elimina cualquier producto de cualquier empresa."""

    permission_classes = [EsAdmin]

    def patch(self, request, producto_id):
        producto = get_object_or_404(Producto, id=producto_id)
        serializer = ProductoAdminSerializer(producto, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_PRODUCTO', producto.id, {'nombre': producto.nombre}, entidad_afectada='producto')
        return Response(ProductoAdminSerializer(producto, context={'request': request}).data)

    def delete(self, request, producto_id):
        producto = get_object_or_404(Producto, id=producto_id)
        nombre = producto.nombre
        producto.delete()
        _log(request, 'ELIMINAR_PRODUCTO', producto_id, {'nombre': nombre}, entidad_afectada='producto')
        return Response(status=status.HTTP_204_NO_CONTENT)


class ImagenProductoAdminView(APIView):
    """CU07: agrega una imagen a un producto — subiendo un archivo
    (multipart, campo "archivo") o pegando una URL externa (campo "url") —
    o la quita (DELETE)."""

    permission_classes = [EsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, producto_id):
        producto = get_object_or_404(Producto, id=producto_id)
        archivo = request.FILES.get('archivo')
        url = (request.data.get('url') or '').strip()
        if not archivo and not url:
            return Response({'detail': 'Sube un archivo o indica una URL.'}, status=status.HTTP_400_BAD_REQUEST)

        siguiente_orden = producto.imagenes.count() + 1
        imagen = ProductoImagen.objects.create(
            producto=producto, archivo=archivo, url=url, orden=siguiente_orden
        )
        return Response(ProductoImagenSerializer(imagen, context={'request': request}).data, status=status.HTTP_201_CREATED)

    def delete(self, request, producto_id, imagen_id):
        ProductoImagen.objects.filter(id=imagen_id, producto_id=producto_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
