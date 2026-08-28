from django.urls import path

from .views import (
    AjustarStockAdminView,
    EditarInventarioAdminView,
    ListaInventarioAdminView,
    ListaSucursalesAdminView,
)

urlpatterns = [
    # CU10: gestión de inventario y stock (SuperAdmin/Admin de soporte)
    path('admin/sucursales/', ListaSucursalesAdminView.as_view(), name='admin-sucursales'),
    path('admin/inventario/', ListaInventarioAdminView.as_view(), name='admin-inventario'),
    path('admin/inventario/<int:inventario_id>/', EditarInventarioAdminView.as_view(), name='admin-inventario-detalle'),
    path('admin/inventario/<int:inventario_id>/ajustar-stock/', AjustarStockAdminView.as_view(), name='admin-inventario-ajustar-stock'),
]
