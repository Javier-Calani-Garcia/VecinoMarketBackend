from django.urls import path

from .views import (
    EditarEliminarMetodoPagoAdminView,
    EditarEliminarMiMetodoPagoView,
    ListaCrearMetodoPagoAdminView,
    ListaCrearMisMetodosPagoView,
)

urlpatterns = [
    # CU25: métodos de pago de las empresas (SuperAdmin/Admin de soporte)
    path('admin/metodos-pago/', ListaCrearMetodoPagoAdminView.as_view(), name='admin-metodos-pago'),
    path('admin/metodos-pago/<int:metodo_id>/', EditarEliminarMetodoPagoAdminView.as_view(), name='admin-metodo-pago-detalle'),

    # CU25: autogestión — la empresa (dueño o empleado con permiso) sobre los suyos
    path('mis-metodos-pago/', ListaCrearMisMetodosPagoView.as_view(), name='mis-metodos-pago'),
    path('mis-metodos-pago/<int:metodo_id>/', EditarEliminarMiMetodoPagoView.as_view(), name='mi-metodo-pago-detalle'),
]
