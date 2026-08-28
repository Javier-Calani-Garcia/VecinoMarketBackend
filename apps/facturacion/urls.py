from django.urls import path

from .views import (
    EditarEliminarFacturaAdminView,
    EditarEliminarMetodoPagoAdminView,
    EditarEliminarMiFacturaView,
    EditarEliminarMiMetodoPagoView,
    ListaCrearMetodoPagoAdminView,
    ListaCrearMisMetodosPagoView,
    ListaFacturasAdminView,
    ListaMisFacturasView,
)

urlpatterns = [
    # CU25: métodos de pago de las empresas (SuperAdmin/Admin de soporte)
    path('admin/metodos-pago/', ListaCrearMetodoPagoAdminView.as_view(), name='admin-metodos-pago'),
    path('admin/metodos-pago/<int:metodo_id>/', EditarEliminarMetodoPagoAdminView.as_view(), name='admin-metodo-pago-detalle'),

    # CU25: autogestión — la empresa (dueño o empleado con permiso) sobre los suyos
    path('mis-metodos-pago/', ListaCrearMisMetodosPagoView.as_view(), name='mis-metodos-pago'),
    path('mis-metodos-pago/<int:metodo_id>/', EditarEliminarMiMetodoPagoView.as_view(), name='mi-metodo-pago-detalle'),

    # CU26: facturación y comisiones (SuperAdmin/Admin de soporte)
    path('admin/facturas/', ListaFacturasAdminView.as_view(), name='admin-facturas'),
    path('admin/facturas/<int:factura_id>/', EditarEliminarFacturaAdminView.as_view(), name='admin-factura-detalle'),

    # CU26: autogestión — la empresa sobre sus propias facturas
    path('mis-facturas/', ListaMisFacturasView.as_view(), name='mis-facturas'),
    path('mis-facturas/<int:factura_id>/', EditarEliminarMiFacturaView.as_view(), name='mi-factura-detalle'),
]
