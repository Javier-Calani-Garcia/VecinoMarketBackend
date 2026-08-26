from django.urls import path

from .views import DetalleProductoView, ListaCategoriasView, ListaProductosView

urlpatterns = [
    path('categorias/', ListaCategoriasView.as_view(), name='catalogo-categorias'),
    path('productos/', ListaProductosView.as_view(), name='catalogo-productos'),
    path('productos/<int:pk>/', DetalleProductoView.as_view(), name='catalogo-producto-detalle'),
]
