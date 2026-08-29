from django.urls import path

from .views import (
    BloquearEmpresaLiveAdminView,
    DarDeBajaLiveAdminView,
    EditarEliminarMiLiveView,
    EditarEliminarMiPromocionView,
    EditarEliminarPromocionAdminView,
    ListaCrearMisLivesView,
    ListaCrearMisPromocionesView,
    ListaLivesAdminView,
    ListaLivesPublicoView,
    ListaPromocionesAdminView,
    ListaResumenEmpresasPromocionesAdminView,
)

urlpatterns = [
    # CU16: promociones y descuentos (SuperAdmin/Admin de soporte)
    path('admin/resumen-empresas/', ListaResumenEmpresasPromocionesAdminView.as_view(), name='admin-resumen-empresas-promociones'),
    path('admin/promociones/', ListaPromocionesAdminView.as_view(), name='admin-promociones'),
    path('admin/promociones/<int:promocion_id>/', EditarEliminarPromocionAdminView.as_view(), name='admin-promocion-detalle'),

    # CU16: autogestión — la empresa (dueño o empleado con permiso) sobre las suyas
    path('mis-promociones/', ListaCrearMisPromocionesView.as_view(), name='mis-promociones'),
    path('mis-promociones/<int:promocion_id>/', EditarEliminarMiPromocionView.as_view(), name='mi-promocion-detalle'),

    # CU17: live commerce — público (botón "LIVE")
    path('lives/', ListaLivesPublicoView.as_view(), name='lives-publico'),

    # CU17: autogestión — la empresa emite sus propios lives
    path('mis-lives/', ListaCrearMisLivesView.as_view(), name='mis-lives'),
    path('mis-lives/<int:live_id>/', EditarEliminarMiLiveView.as_view(), name='mi-live-detalle'),

    # CU17: SuperAdmin/Admin de soporte
    path('admin/lives/', ListaLivesAdminView.as_view(), name='admin-lives'),
    path('admin/lives/<int:live_id>/dar-de-baja/', DarDeBajaLiveAdminView.as_view(), name='admin-live-dar-de-baja'),
    path('admin/empresas/<int:empresa_id>/bloquear-live/', BloquearEmpresaLiveAdminView.as_view(), name='admin-empresa-bloquear-live'),
]
