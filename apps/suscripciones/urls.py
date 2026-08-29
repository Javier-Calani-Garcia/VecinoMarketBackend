from django.urls import path

from .views import (
    EditarEliminarPlanAdminView,
    EditarSuscripcionEmpresaView,
    ExpirarSuscripcionesView,
    ListaCrearPlanAdminView,
    ListaPlanesView,
)

urlpatterns = [
    path('planes/', ListaPlanesView.as_view(), name='lista_planes'),
    path('empresas/<int:empresa_id>/suscripcion/', EditarSuscripcionEmpresaView.as_view(), name='editar_suscripcion_empresa'),
    path('expirar-vencidas/', ExpirarSuscripcionesView.as_view(), name='expirar_suscripciones_vencidas'),

    # CU20: catálogo completo de planes (crear/editar/eliminar)
    path('admin/planes/', ListaCrearPlanAdminView.as_view(), name='admin-planes'),
    path('admin/planes/<int:plan_id>/', EditarEliminarPlanAdminView.as_view(), name='admin-plan-detalle'),
]
