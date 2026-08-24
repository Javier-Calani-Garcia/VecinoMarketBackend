from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip

from .models import Usuario
from .permissions import EsAdminEmpresa, EsSuperAdmin
from .serializers import (
    CrearEmpleadoSerializer,
    CrearEmpresaConAdminSerializer,
    LoginSerializer,
    RegistroClienteSerializer,
    UsuarioSerializer,
)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class CrearEmpresaView(CreateAPIView):
    """El superadmin crea una empresa (tenant) junto con su usuario admin."""

    permission_classes = [EsSuperAdmin]
    serializer_class = CrearEmpresaConAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resultado = serializer.save()

        LogAuditoria.objects.create(
            usuario=request.user,
            empresa=resultado['empresa'],
            accion='CREAR_EMPRESA',
            objeto_id=str(resultado['empresa'].id),
            ip=get_client_ip(request),
        )

        return Response(
            {
                'empresa': {'id': resultado['empresa'].id, 'nombre': resultado['empresa'].nombre},
                'admin': {'id': resultado['admin'].id, 'email': resultado['admin'].email},
            },
            status=status.HTTP_201_CREATED,
        )


class ListaEmpresasView(ListAPIView):
    permission_classes = [EsSuperAdmin]
    serializer_class = UsuarioSerializer  # placeholder simple; en catalogo/reportes se amplía

    def get_queryset(self):
        from .models import Empresa
        return Empresa.objects.all()


class CrearEmpleadoView(CreateAPIView):
    """El admin de empresa crea empleados dentro de su propio tenant."""

    permission_classes = [EsAdminEmpresa]
    serializer_class = CrearEmpleadoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empleado = serializer.save()

        LogAuditoria.objects.create(
            usuario=request.user,
            empresa=request.user.empresa,
            accion='CREAR_EMPLEADO',
            objeto_id=str(empleado.id),
            ip=get_client_ip(request),
        )

        return Response(UsuarioSerializer(empleado).data, status=status.HTTP_201_CREATED)


class ListaEmpleadosView(ListAPIView):
    permission_classes = [EsAdminEmpresa]
    serializer_class = UsuarioSerializer

    def get_queryset(self):
        return Usuario.objects.filter(
            rol=Usuario.Rol.EMPLEADO, empresa=self.request.user.empresa
        )


class DesactivarEmpleadoView(APIView):
    permission_classes = [EsAdminEmpresa]

    def post(self, request, empleado_id):
        empleado = get_object_or_404(
            Usuario, id=empleado_id, rol=Usuario.Rol.EMPLEADO, empresa=request.user.empresa
        )
        empleado.is_active = False
        empleado.save(update_fields=['is_active'])

        for token in OutstandingToken.objects.filter(user=empleado):
            BlacklistedToken.objects.get_or_create(token=token)

        LogAuditoria.objects.create(
            usuario=request.user,
            empresa=request.user.empresa,
            accion='DESACTIVAR_EMPLEADO',
            objeto_id=str(empleado.id),
            ip=get_client_ip(request),
        )
        return Response({'detail': 'Empleado desactivado.'}, status=status.HTTP_200_OK)


class ReactivarEmpleadoView(APIView):
    permission_classes = [EsAdminEmpresa]

    def post(self, request, empleado_id):
        empleado = get_object_or_404(
            Usuario, id=empleado_id, rol=Usuario.Rol.EMPLEADO, empresa=request.user.empresa
        )
        empleado.is_active = True
        empleado.save(update_fields=['is_active'])

        LogAuditoria.objects.create(
            usuario=request.user,
            empresa=request.user.empresa,
            accion='REACTIVAR_EMPLEADO',
            objeto_id=str(empleado.id),
            ip=get_client_ip(request),
        )
        return Response({'detail': 'Empleado reactivado.'}, status=status.HTTP_200_OK)


class RegistroClienteView(CreateAPIView):
    """Registro público: cualquiera puede crear su cuenta de cliente."""

    permission_classes = [AllowAny]
    serializer_class = RegistroClienteSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cliente = serializer.save()
        return Response(UsuarioSerializer(cliente).data, status=status.HTTP_201_CREATED)


class PerfilView(APIView):
    """Devuelve los datos del usuario autenticado (para pintar el menú según su rol)."""

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)
