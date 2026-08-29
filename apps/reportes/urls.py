from django.urls import path

from .views import (
    EditarEliminarMiValoracionView,
    EliminarValoracionAdminView,
    ListaCrearMisValoracionesView,
    ListaResumenEmpresasValoracionesAdminView,
    ListaValoracionesAdminView,
    ListaValoracionesEmpresaView,
)

urlpatterns = [
    # CU04: el comprador califica sus pedidos entregados
    path('mis-valoraciones/', ListaCrearMisValoracionesView.as_view(), name='mis-valoraciones'),
    path('mis-valoraciones/<int:valoracion_id>/', EditarEliminarMiValoracionView.as_view(), name='mi-valoracion-detalle'),

    # CU04: la empresa ve (solo lectura) las que recibió
    path('mis-valoraciones-recibidas/', ListaValoracionesEmpresaView.as_view(), name='mis-valoraciones-recibidas'),

    # CU04: SuperAdmin/Admin de soporte
    path('admin/resumen-valoraciones-empresas/', ListaResumenEmpresasValoracionesAdminView.as_view(), name='admin-resumen-valoraciones-empresas'),
    path('admin/valoraciones/', ListaValoracionesAdminView.as_view(), name='admin-valoraciones'),
    path('admin/valoraciones/<int:valoracion_id>/', EliminarValoracionAdminView.as_view(), name='admin-valoracion-detalle'),
]
