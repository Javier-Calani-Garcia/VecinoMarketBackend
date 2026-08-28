from django.urls import path

from .views import AsignarPlanEmpresaView, ExpirarSuscripcionesView, ListaPlanesView

urlpatterns = [
    path('planes/', ListaPlanesView.as_view(), name='lista_planes'),
    path('empresas/<int:empresa_id>/asignar-plan/', AsignarPlanEmpresaView.as_view(), name='asignar_plan_empresa'),
    path('expirar-vencidas/', ExpirarSuscripcionesView.as_view(), name='expirar_suscripciones_vencidas'),
]
