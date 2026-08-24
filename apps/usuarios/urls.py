from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    CrearEmpleadoView,
    CrearEmpresaView,
    DesactivarEmpleadoView,
    ListaEmpleadosView,
    ListaEmpresasView,
    LoginView,
    PerfilView,
    ReactivarEmpleadoView,
    RegistroClienteView,
)

urlpatterns = [
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/perfil/', PerfilView.as_view(), name='perfil'),

    path('empresas/', CrearEmpresaView.as_view(), name='crear_empresa'),
    path('empresas/lista/', ListaEmpresasView.as_view(), name='lista_empresas'),

    path('empleados/', CrearEmpleadoView.as_view(), name='crear_empleado'),
    path('empleados/lista/', ListaEmpleadosView.as_view(), name='lista_empleados'),
    path('empleados/<int:empleado_id>/desactivar/', DesactivarEmpleadoView.as_view(), name='desactivar_empleado'),
    path('empleados/<int:empleado_id>/reactivar/', ReactivarEmpleadoView.as_view(), name='reactivar_empleado'),

    path('clientes/registro/', RegistroClienteView.as_view(), name='registro_cliente'),
]
