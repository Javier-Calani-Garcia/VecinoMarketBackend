from django.urls import path

from .views import EditarSuscripcionEmpresaView, ExpirarSuscripcionesView, ListaPlanesView

urlpatterns = [
    path('planes/', ListaPlanesView.as_view(), name='lista_planes'),
    path('empresas/<int:empresa_id>/suscripcion/', EditarSuscripcionEmpresaView.as_view(), name='editar_suscripcion_empresa'),
    path('expirar-vencidas/', ExpirarSuscripcionesView.as_view(), name='expirar_suscripciones_vencidas'),
]
