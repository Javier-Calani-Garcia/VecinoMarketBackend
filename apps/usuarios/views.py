from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip

from .models import Empleado, Empresa, Permiso, RolBase, RolBasePermiso, SolicitudEmpresa, Usuario
from .permissions import EsAdmin, EsEmpresa
from .serializers import (
    ActualizarPerfilSerializer,
    AprobarSolicitudSerializer,
    CambiarPasswordSerializer,
    ConfirmarResetPasswordSerializer,
    CrearEmpleadoSerializer,
    EmpresaAdminSerializer,
    GoogleAuthSerializer,
    LoginSerializer,
    PermisoSerializer,
    RechazarSolicitudSerializer,
    RegistroCompradorSerializer,
    RolBaseSerializer,
    SolicitarResetPasswordSerializer,
    SolicitudEmpresaSerializer,
    UsuarioSerializer,
)


def _log(request, accion, entidad_afectada=None, entidad_id=None, detalle=None, usuario=None):
    LogAuditoria.objects.create(
        usuario=usuario if usuario is not None else (request.user if request.user.is_authenticated else None),
        accion=accion,
        entidad_afectada=entidad_afectada,
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class LoginView(TokenObtainPairView):
    """CU22: cada login exitoso queda registrado en la bitácora (usuario, fecha/hora, IP)."""

    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK:
            usuario = Usuario.objects.filter(email=request.data.get('email')).first()
            if usuario:
                _log(request, 'LOGIN', 'usuario', usuario.id, usuario=usuario)
        return response


class LogoutView(APIView):
    """CU22: cada logout queda registrado en la bitácora, e invalida el refresh token."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = request.data.get('refresh')
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass

        _log(request, 'LOGOUT', 'usuario', request.user.id)
        return Response({'detail': 'Sesión cerrada.'}, status=status.HTTP_200_OK)


class GoogleAuthView(APIView):
    """Login o registro automático con Google (Identity Services). CU22:
    igual que el login normal, queda registrado en la bitácora."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario, creado = serializer.save()

        if usuario.estado != Usuario.Estado.ACTIVO:
            return Response({'detail': 'Tu cuenta no está activa.'}, status=status.HTTP_403_FORBIDDEN)

        refresh = LoginSerializer.get_token(usuario)

        _log(request, 'REGISTRO_GOOGLE' if creado else 'LOGIN_GOOGLE', 'usuario', usuario.id, usuario=usuario)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'nuevo': creado,
        })


class SolicitarEmpresaView(CreateAPIView):
    """CU01: un usuario autenticado solicita convertirse en empresa."""

    permission_classes = [IsAuthenticated]
    serializer_class = SolicitudEmpresaSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        solicitud = serializer.save()

        _log(request, 'SOLICITAR_EMPRESA', 'solicitud_empresa', solicitud.id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ListaSolicitudesEmpresaView(ListAPIView):
    """CU01: el admin revisa las solicitudes pendientes."""

    permission_classes = [EsAdmin]
    serializer_class = SolicitudEmpresaSerializer

    def get_queryset(self):
        return SolicitudEmpresa.objects.filter(estado=SolicitudEmpresa.Estado.PENDIENTE)


class AprobarSolicitudEmpresaView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, solicitud_id):
        solicitud = get_object_or_404(
            SolicitudEmpresa, id=solicitud_id, estado=SolicitudEmpresa.Estado.PENDIENTE
        )
        serializer = AprobarSolicitudSerializer(
            data=request.data, context={'request': request, 'solicitud': solicitud}
        )
        serializer.is_valid(raise_exception=True)
        empresa = serializer.save()

        _log(request, 'APROBAR_EMPRESA', 'empresa', empresa.id)
        return Response({'id': empresa.id, 'slug': empresa.slug}, status=status.HTTP_200_OK)


class RechazarSolicitudEmpresaView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, solicitud_id):
        solicitud = get_object_or_404(
            SolicitudEmpresa, id=solicitud_id, estado=SolicitudEmpresa.Estado.PENDIENTE
        )
        serializer = RechazarSolicitudSerializer(
            data=request.data, context={'request': request, 'solicitud': solicitud}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _log(request, 'RECHAZAR_EMPRESA', 'solicitud_empresa', solicitud.id)
        return Response({'detail': 'Solicitud rechazada.'}, status=status.HTTP_200_OK)


class CrearEmpleadoView(CreateAPIView):
    """CU09: la empresa crea empleados dentro de su propio tenant."""

    permission_classes = [EsEmpresa]
    serializer_class = CrearEmpleadoSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        empleado = serializer.save()

        _log(request, 'CREAR_EMPLEADO', 'empleado', empleado.id)
        return Response(UsuarioSerializer(empleado.usuario).data, status=status.HTTP_201_CREATED)


class ListaEmpleadosView(ListAPIView):
    permission_classes = [EsEmpresa]
    serializer_class = UsuarioSerializer

    def get_queryset(self):
        empresa = self.request.user.get_empresa()
        return Usuario.objects.filter(empleado__empresa=empresa)


class DesactivarEmpleadoView(APIView):
    permission_classes = [EsEmpresa]

    def post(self, request, empleado_id):
        empresa = request.user.get_empresa()
        empleado = get_object_or_404(Empleado, id=empleado_id, empresa=empresa)

        empleado.usuario.is_active = False
        empleado.usuario.estado = Usuario.Estado.INACTIVO
        empleado.usuario.save(update_fields=['is_active', 'estado'])
        empleado.estado = Empleado.Estado.INACTIVO
        empleado.save(update_fields=['estado'])

        for token in OutstandingToken.objects.filter(user=empleado.usuario):
            BlacklistedToken.objects.get_or_create(token=token)

        _log(request, 'DESACTIVAR_EMPLEADO', 'empleado', empleado.id)
        return Response({'detail': 'Empleado desactivado.'}, status=status.HTTP_200_OK)


class ReactivarEmpleadoView(APIView):
    permission_classes = [EsEmpresa]

    def post(self, request, empleado_id):
        empresa = request.user.get_empresa()
        empleado = get_object_or_404(Empleado, id=empleado_id, empresa=empresa)

        empleado.usuario.is_active = True
        empleado.usuario.estado = Usuario.Estado.ACTIVO
        empleado.usuario.save(update_fields=['is_active', 'estado'])
        empleado.estado = Empleado.Estado.ACTIVO
        empleado.save(update_fields=['estado'])

        _log(request, 'REACTIVAR_EMPLEADO', 'empleado', empleado.id)
        return Response({'detail': 'Empleado reactivado.'}, status=status.HTTP_200_OK)


class RegistroCompradorView(CreateAPIView):
    """Registro público: cualquiera puede crear su cuenta de comprador.

    Devuelve el JWT directamente (igual que el login) para no forzar un
    segundo login inmediatamente después, que exigiría un segundo reCAPTCHA.
    """

    permission_classes = [AllowAny]
    serializer_class = RegistroCompradorSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comprador = serializer.save()

        refresh = LoginSerializer.get_token(comprador)
        _log(request, 'REGISTRO', 'usuario', comprador.id, usuario=comprador)

        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'usuario': UsuarioSerializer(comprador).data,
        }, status=status.HTTP_201_CREATED)


class PerfilView(APIView):
    """Devuelve y permite editar los datos del usuario autenticado (CU/T013, RF07)."""

    def get(self, request):
        return Response(UsuarioSerializer(request.user).data)

    def patch(self, request):
        serializer = ActualizarPerfilSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'ACTUALIZAR_PERFIL', 'usuario', request.user.id)
        return Response(UsuarioSerializer(request.user).data)


class CambiarPasswordView(APIView):
    """T013 (RF07): el usuario cambia su propia contraseña, confirmando la actual."""

    def post(self, request):
        serializer = CambiarPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'CAMBIAR_PASSWORD', 'usuario', request.user.id)
        return Response({'detail': 'Contraseña actualizada correctamente.'})


class SolicitarResetPasswordView(APIView):
    """T010 (RF03): pide el email y, si existe, envía el link de recuperación."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SolicitarResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'SOLICITAR_RESET_PASSWORD', 'usuario', detalle={'email': request.data.get('email')})
        return Response({'detail': 'Si el correo está registrado, te enviamos un link para restablecer tu contraseña.'})


class ConfirmarResetPasswordView(APIView):
    """T010 (RF03): confirma el link (uid + token) y guarda la nueva contraseña."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConfirmarResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usuario = serializer.save()

        for token in OutstandingToken.objects.filter(user=usuario):
            BlacklistedToken.objects.get_or_create(token=token)

        _log(request, 'RESTABLECER_PASSWORD', 'usuario', usuario.id, usuario=usuario)
        return Response({'detail': 'Contraseña actualizada correctamente. Ya puedes ingresar.'})


# =====================================================================
# T009 (RF01/RF02): gestión de usuarios y cuentas empresariales — ADMIN
# =====================================================================

class AdminPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


class ListaUsuariosView(ListAPIView):
    """El ADMIN ve y filtra todos los usuarios de la plataforma."""

    permission_classes = [EsAdmin]
    serializer_class = UsuarioSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = Usuario.objects.all().order_by('-fecha_registro')

        rol = self.request.query_params.get('rol')
        if rol:
            queryset = queryset.filter(rol=rol)

        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(email__icontains=q) | Q(nombre__icontains=q))

        return queryset


class BloquearUsuarioView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, usuario_id):
        if usuario_id == request.user.id:
            return Response({'detail': 'No puedes bloquear tu propia cuenta.'}, status=status.HTTP_400_BAD_REQUEST)

        usuario = get_object_or_404(Usuario, id=usuario_id)
        usuario.estado = Usuario.Estado.BLOQUEADO
        usuario.is_active = False
        usuario.save(update_fields=['estado', 'is_active'])

        for token in OutstandingToken.objects.filter(user=usuario):
            BlacklistedToken.objects.get_or_create(token=token)

        _log(request, 'BLOQUEAR_USUARIO', 'usuario', usuario.id)
        return Response({'detail': 'Usuario bloqueado.'})


class DesbloquearUsuarioView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, usuario_id):
        usuario = get_object_or_404(Usuario, id=usuario_id)
        usuario.estado = Usuario.Estado.ACTIVO
        usuario.is_active = True
        usuario.save(update_fields=['estado', 'is_active'])

        _log(request, 'DESBLOQUEAR_USUARIO', 'usuario', usuario.id)
        return Response({'detail': 'Usuario desbloqueado.'})


class ListaEmpresasAdminView(ListAPIView):
    """El ADMIN ve y filtra todas las empresas (no solo las solicitudes pendientes)."""

    permission_classes = [EsAdmin]
    serializer_class = EmpresaAdminSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = Empresa.objects.select_related('usuario_dueno').order_by('-creado_en')

        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(razon_social__icontains=q) | Q(nit__icontains=q))

        return queryset


class SuspenderEmpresaView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, empresa_id):
        empresa = get_object_or_404(Empresa, id=empresa_id)
        empresa.estado = Empresa.Estado.SUSPENDIDA
        empresa.save(update_fields=['estado'])
        _log(request, 'SUSPENDER_EMPRESA', 'empresa', empresa.id)
        return Response({'detail': 'Empresa suspendida.'})


class ReactivarEmpresaView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, empresa_id):
        empresa = get_object_or_404(Empresa, id=empresa_id)
        empresa.estado = Empresa.Estado.ACTIVA
        empresa.save(update_fields=['estado'])
        _log(request, 'REACTIVAR_EMPRESA', 'empresa', empresa.id)
        return Response({'detail': 'Empresa reactivada.'})


# =====================================================================
# T054/T055 (RF53/RF54): roles administrativos globales y sus permisos
# =====================================================================

class ListaPermisosView(ListAPIView):
    """Catálogo de permisos disponibles en la plataforma (solo lectura)."""

    permission_classes = [EsAdmin]
    serializer_class = PermisoSerializer
    pagination_class = None
    queryset = Permiso.objects.all().order_by('codigo')


class ListaCrearRolBaseView(ListCreateAPIView):
    """T054: el ADMIN crea y lista los roles base de la plataforma."""

    permission_classes = [EsAdmin]
    serializer_class = RolBaseSerializer
    pagination_class = None
    queryset = RolBase.objects.all().order_by('nombre')

    def perform_create(self, serializer):
        rol = serializer.save()
        _log(self.request, 'CREAR_ROL_BASE', 'rol_base', rol.id)


class EliminarRolBaseView(APIView):
    permission_classes = [EsAdmin]

    def delete(self, request, rol_id):
        rol = get_object_or_404(RolBase, id=rol_id)
        rol.delete()
        _log(request, 'ELIMINAR_ROL_BASE', 'rol_base', rol_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermisoRolBaseView(APIView):
    """T055: asigna (POST) o quita (DELETE) un permiso del catálogo a un rol base."""

    permission_classes = [EsAdmin]

    def post(self, request, rol_id, permiso_id):
        rol = get_object_or_404(RolBase, id=rol_id)
        permiso = get_object_or_404(Permiso, id=permiso_id)
        RolBasePermiso.objects.get_or_create(rol_base=rol, permiso=permiso)
        _log(request, 'ASIGNAR_PERMISO_ROL', 'rol_base', rol.id, detalle={'permiso': permiso.codigo})
        return Response(RolBaseSerializer(rol).data)

    def delete(self, request, rol_id, permiso_id):
        rol = get_object_or_404(RolBase, id=rol_id)
        RolBasePermiso.objects.filter(rol_base_id=rol_id, permiso_id=permiso_id).delete()
        _log(request, 'QUITAR_PERMISO_ROL', 'rol_base', rol_id, detalle={'permiso_id': permiso_id})
        return Response(RolBaseSerializer(rol).data)
