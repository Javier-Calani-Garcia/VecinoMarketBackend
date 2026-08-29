from django.core.files.storage import default_storage
from django.db import connection
from django.db.models import OuterRef, Q, Subquery
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import CreateAPIView, ListAPIView, ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.suscripciones.models import Suscripcion

from .models import Comprador, Direccion, Empleado, EmpleadoPermiso, Empresa, Permiso, RolBase, RolBasePermiso, SolicitudEmpresa, Usuario
from .permissions import EsAdmin, EsComprador, EsEmpresa, EsSuperAdmin
from .serializers import (
    ActualizarPerfilAdminSerializer,
    ActualizarPerfilSerializer,
    AprobarSolicitudSerializer,
    CambiarPasswordSerializer,
    CambiarRolSerializer,
    ConfirmarResetPasswordSerializer,
    CrearEmpleadoSerializer,
    DireccionSerializer,
    EditarEmpresaAdminSerializer,
    EditarMiEmpresaSerializer,
    EmpresaPublicaSerializer,
    EditarUsuarioAdminSerializer,
    EmpleadoAdminSerializer,
    EmpresaAdminSerializer,
    GoogleAuthSerializer,
    LoginSerializer,
    PermisoSerializer,
    RechazarSolicitudSerializer,
    RegistrarUsuarioAdminSerializer,
    RegistroCompradorSerializer,
    RestablecerPasswordAdminSerializer,
    RolBaseSerializer,
    SolicitarResetPasswordSerializer,
    SolicitudEmpresaSerializer,
    UsuarioSerializer,
)


class AdminPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


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
    serializer_class = EmpleadoAdminSerializer

    def get_queryset(self):
        empresa = self.request.user.get_empresa()
        return Empleado.objects.filter(empresa=empresa).select_related('usuario', 'empresa').order_by('-creado_en')


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


class PermisoEmpleadoPropioView(APIView):
    """CU09: la empresa asigna (POST) o quita (DELETE) un permiso a UNO DE
    SUS PROPIOS empleados — el filtro por `empresa=` en el get_object_or_404
    es la verificación de tenant: sin él, una empresa podría tocar los
    permisos de un empleado de otra adivinando su id."""

    permission_classes = [EsEmpresa]

    def post(self, request, empleado_id, permiso_id):
        empresa = request.user.get_empresa()
        empleado = get_object_or_404(Empleado, id=empleado_id, empresa=empresa)
        permiso = get_object_or_404(Permiso, id=permiso_id)
        EmpleadoPermiso.objects.get_or_create(empleado=empleado, permiso=permiso)
        _log(request, 'ASIGNAR_PERMISO_EMPLEADO', 'empleado', empleado.id, detalle={'permiso': permiso.codigo})
        return Response(EmpleadoAdminSerializer(empleado).data)

    def delete(self, request, empleado_id, permiso_id):
        empresa = request.user.get_empresa()
        empleado = get_object_or_404(Empleado, id=empleado_id, empresa=empresa)
        EmpleadoPermiso.objects.filter(empleado=empleado, permiso_id=permiso_id).delete()
        _log(request, 'QUITAR_PERMISO_EMPLEADO', 'empleado', empleado.id, detalle={'permiso_id': permiso_id})
        return Response(EmpleadoAdminSerializer(empleado).data)


# =====================================================================
# CU09: el SuperAdmin gestiona empleados de CUALQUIER empresa y sus
# permisos (a diferencia de las vistas de arriba, que son la propia
# empresa administrando solo lo suyo).
# =====================================================================

class ListaEmpleadosAdminView(ListAPIView):
    permission_classes = [EsAdmin]
    serializer_class = EmpleadoAdminSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        queryset = Empleado.objects.select_related('usuario', 'empresa').order_by('-creado_en')

        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            queryset = queryset.filter(empresa_id=empresa_id)

        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(
                Q(usuario__nombre__icontains=q)
                | Q(usuario__email__icontains=q)
                | Q(empresa__razon_social__icontains=q)
            )

        return queryset


class DesactivarEmpleadoAdminView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, empleado_id):
        empleado = get_object_or_404(Empleado, id=empleado_id)

        empleado.usuario.is_active = False
        empleado.usuario.estado = Usuario.Estado.INACTIVO
        empleado.usuario.save(update_fields=['is_active', 'estado'])
        empleado.estado = Empleado.Estado.INACTIVO
        empleado.save(update_fields=['estado'])

        for token in OutstandingToken.objects.filter(user=empleado.usuario):
            BlacklistedToken.objects.get_or_create(token=token)

        _log(request, 'DESACTIVAR_EMPLEADO_ADMIN', 'empleado', empleado.id)
        return Response({'detail': 'Empleado desactivado.'})


class ReactivarEmpleadoAdminView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, empleado_id):
        empleado = get_object_or_404(Empleado, id=empleado_id)

        empleado.usuario.is_active = True
        empleado.usuario.estado = Usuario.Estado.ACTIVO
        empleado.usuario.save(update_fields=['is_active', 'estado'])
        empleado.estado = Empleado.Estado.ACTIVO
        empleado.save(update_fields=['estado'])

        _log(request, 'REACTIVAR_EMPLEADO_ADMIN', 'empleado', empleado.id)
        return Response({'detail': 'Empleado reactivado.'})


class PermisoEmpleadoAdminView(APIView):
    """CU09: asigna (POST) o quita (DELETE) un permiso del catálogo a un
    empleado — define a qué partes del panel de su empresa tiene acceso."""

    permission_classes = [EsAdmin]

    def post(self, request, empleado_id, permiso_id):
        empleado = get_object_or_404(Empleado, id=empleado_id)
        permiso = get_object_or_404(Permiso, id=permiso_id)
        EmpleadoPermiso.objects.get_or_create(empleado=empleado, permiso=permiso)
        _log(request, 'ASIGNAR_PERMISO_EMPLEADO', 'empleado', empleado.id, detalle={'permiso': permiso.codigo})
        return Response(EmpleadoAdminSerializer(empleado).data)

    def delete(self, request, empleado_id, permiso_id):
        empleado = get_object_or_404(Empleado, id=empleado_id)
        EmpleadoPermiso.objects.filter(empleado_id=empleado_id, permiso_id=permiso_id).delete()
        _log(request, 'QUITAR_PERMISO_EMPLEADO', 'empleado', empleado_id, detalle={'permiso_id': permiso_id})
        return Response(EmpleadoAdminSerializer(empleado).data)


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
        serializer_class = (
            ActualizarPerfilAdminSerializer if request.user.es_admin() else ActualizarPerfilSerializer
        )
        serializer = serializer_class(request.user, data=request.data, partial=True)
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


class RegistrarUsuarioAdminView(CreateAPIView):
    """CU02: el ADMIN registra un usuario (comprador) directamente desde su panel."""

    permission_classes = [EsAdmin]
    serializer_class = RegistrarUsuarioAdminSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nuevo_usuario = serializer.save()

        _log(request, 'REGISTRAR_USUARIO_ADMIN', 'usuario', nuevo_usuario.id)
        return Response(UsuarioSerializer(nuevo_usuario).data, status=status.HTTP_201_CREATED)


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


class EditarUsuarioAdminView(APIView):
    """CU02/CU03: el personal de la plataforma edita datos (email, nombre,
    apellido, teléfono, estado) de cualquier usuario. El rol NO se toca acá
    — eso es CU24 (CambiarRolUsuarioView), exclusivo del SuperAdmin. Un
    ADMIN de soporte tampoco puede editar a un SUPERADMIN."""

    permission_classes = [EsAdmin]

    def patch(self, request, usuario_id):
        usuario_obj = get_object_or_404(Usuario, id=usuario_id)
        if usuario_obj.es_superadmin() and not request.user.es_superadmin():
            return Response(
                {'detail': 'No puedes editar a un Super administrador.'}, status=status.HTTP_403_FORBIDDEN
            )

        serializer = EditarUsuarioAdminSerializer(usuario_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _log(request, 'EDITAR_USUARIO_ADMIN', 'usuario', usuario_obj.id)
        return Response(UsuarioSerializer(usuario_obj).data)


class RestablecerPasswordAdminView(APIView):
    """CU03: el SuperAdmin restablece la contraseña de cualquier usuario.
    Exclusivo de SUPERADMIN: un ADMIN de soporte no debe poder tomar el
    control de ninguna cuenta (ni siquiera de otro ADMIN)."""

    permission_classes = [EsSuperAdmin]

    def post(self, request, usuario_id):
        usuario_obj = get_object_or_404(Usuario, id=usuario_id)
        serializer = RestablecerPasswordAdminSerializer(data=request.data, context={'usuario': usuario_obj})
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _log(request, 'RESTABLECER_PASSWORD_ADMIN', 'usuario', usuario_obj.id)
        return Response({'detail': 'Contraseña restablecida.'})


class CambiarRolUsuarioView(APIView):
    """CU24: el SuperAdmin cambia el rol de cualquier usuario. Exclusivo de
    SUPERADMIN — si un ADMIN de soporte pudiera hacerlo, podría ascenderse
    a sí mismo (o a cualquiera) a SUPERADMIN. Queda registrado en la
    bitácora desde Python (con quién lo hizo) y también vía
    trg_registrar_cambio_rol en la base de datos (red de seguridad para
    cambios hechos fuera de la app)."""

    permission_classes = [EsSuperAdmin]

    def post(self, request, usuario_id):
        usuario_obj = get_object_or_404(Usuario, id=usuario_id)
        serializer = CambiarRolSerializer(data=request.data, context={'usuario': usuario_obj})
        serializer.is_valid(raise_exception=True)
        usuario_obj, rol_anterior = serializer.save()

        _log(
            request, 'CAMBIAR_ROL_USUARIO', 'usuario', usuario_obj.id,
            detalle={'rol_anterior': rol_anterior, 'rol_nuevo': usuario_obj.rol},
        )
        return Response(UsuarioSerializer(usuario_obj).data)


class BloquearUsuarioView(APIView):
    permission_classes = [EsAdmin]

    def post(self, request, usuario_id):
        if usuario_id == request.user.id:
            return Response({'detail': 'No puedes bloquear tu propia cuenta.'}, status=status.HTTP_400_BAD_REQUEST)

        usuario = get_object_or_404(Usuario, id=usuario_id)
        if usuario.es_superadmin() and not request.user.es_superadmin():
            return Response(
                {'detail': 'No puedes bloquear a un Super administrador.'}, status=status.HTTP_403_FORBIDDEN
            )
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


class ListaEmpresasPublicoView(ListAPIView):
    """CU15/CU17: cualquier visitante busca una empresa activa por nombre —
    lo mínimo para elegir a cuál preguntarle al chatbot o ver si está en
    vivo, sin exponer nada del detalle administrativo (EmpresaAdminSerializer)."""

    permission_classes = [AllowAny]
    serializer_class = EmpresaPublicaSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Empresa.objects.filter(estado=Empresa.Estado.ACTIVA).order_by('razon_social')
        q = self.request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(razon_social__icontains=q)
        return qs


class ListaEmpresasAdminView(ListAPIView):
    """CU01: el ADMIN ve y filtra todas las empresas (no solo las solicitudes
    pendientes), incluyendo el estado de su suscripción (activa / solicitando
    suscripción / expirada)."""

    permission_classes = [EsAdmin]
    serializer_class = EmpresaAdminSerializer
    pagination_class = AdminPagination

    def get_queryset(self):
        # Antes de listar, refresca cualquier suscripción que ya venció (lo
        # mismo que hace el comando `expirar_suscripciones`), así el admin
        # nunca ve una empresa como "activa" con una fecha ya pasada.
        with connection.cursor() as cursor:
            cursor.execute('CALL sp_expirar_suscripciones_vencidas();')

        ultima_suscripcion = Suscripcion.objects.filter(empresa=OuterRef('pk')).order_by('-fecha_vencimiento')
        queryset = (
            Empresa.objects.select_related('usuario_dueno', 'plan')
            .annotate(
                _susc_estado=Subquery(ultima_suscripcion.values('estado')[:1]),
                _susc_vencimiento=Subquery(ultima_suscripcion.values('fecha_vencimiento')[:1]),
            )
            .order_by('-creado_en')
        )

        estado = self.request.query_params.get('estado')
        if estado:
            queryset = queryset.filter(estado=estado)

        hoy = timezone.now().date()
        estado_suscripcion = self.request.query_params.get('estado_suscripcion')
        if estado_suscripcion == 'SOLICITANDO_SUSCRIPCION':
            queryset = queryset.filter(Q(plan__isnull=True) | Q(_susc_vencimiento__isnull=True))
        elif estado_suscripcion == 'ACTIVA':
            queryset = queryset.filter(
                plan__isnull=False, _susc_estado=Suscripcion.Estado.ACTIVA, _susc_vencimiento__gte=hoy
            )
        elif estado_suscripcion == 'EXPIRADA':
            queryset = queryset.filter(plan__isnull=False, _susc_vencimiento__isnull=False).exclude(
                _susc_estado=Suscripcion.Estado.ACTIVA, _susc_vencimiento__gte=hoy
            )

        q = self.request.query_params.get('q')
        if q:
            queryset = queryset.filter(Q(razon_social__icontains=q) | Q(nit__icontains=q))

        return queryset


class EditarEmpresaAdminView(APIView):
    """CU01: el SuperAdmin edita cualquier dato de la empresa."""

    permission_classes = [EsAdmin]

    def patch(self, request, empresa_id):
        empresa = get_object_or_404(Empresa, id=empresa_id)
        serializer = EditarEmpresaAdminSerializer(empresa, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        _log(request, 'EDITAR_EMPRESA_ADMIN', 'empresa', empresa.id)
        # No se reusa EmpresaAdminSerializer: sus campos de suscripción
        # dependen de la anotación que solo arma ListaEmpresasAdminView.
        return Response(serializer.data)


class MiEmpresaView(APIView):
    """La empresa ve y edita su propio perfil (razón social, logo, marca,
    descripción, ubicación) — 'slug' y 'estado' quedan fuera de
    EditarMiEmpresaSerializer, así que aunque se manden en el body se
    ignoran; siguen siendo solo del SuperAdmin (EditarEmpresaAdminView)."""

    permission_classes = [EsEmpresa]

    def get(self, request):
        empresa = request.user.get_empresa()
        return Response(EditarMiEmpresaSerializer(empresa).data)

    def patch(self, request):
        empresa = request.user.get_empresa()
        serializer = EditarMiEmpresaSerializer(empresa, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_MI_EMPRESA', 'empresa', empresa.id)
        return Response(serializer.data)


class SubirLogoEmpresaView(APIView):
    """La empresa sube su logo como imagen (campo multipart "archivo") en
    vez de tener que pegar una URL a mano. 'logo_url' se queda como el
    único campo que lee el resto del sistema (tarjetas de producto, header
    admin, etc.) — acá solo lo llenamos con la URL que devuelve el storage
    configurado (Cloudinary en producción, disco en dev sin credenciales)."""

    permission_classes = [EsEmpresa]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        archivo = request.FILES.get('archivo')
        if not archivo:
            return Response({'detail': 'Sube un archivo de imagen.'}, status=status.HTTP_400_BAD_REQUEST)

        empresa = request.user.get_empresa()
        nombre_guardado = default_storage.save(f'empresas/logos/{empresa.slug}-{archivo.name}', archivo)
        empresa.logo_url = default_storage.url(nombre_guardado)
        empresa.save(update_fields=['logo_url'])

        _log(request, 'SUBIR_LOGO_EMPRESA', 'empresa', empresa.id)
        return Response({'logo_url': empresa.logo_url}, status=status.HTTP_201_CREATED)


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
    """Catálogo de permisos disponibles en la plataforma (solo lectura) — lo
    usa tanto el SuperAdmin (admin/Empleados.jsx) como la propia empresa al
    asignarle permisos a sus empleados (empresa/MisEmpleados.jsx)."""

    permission_classes = [EsAdmin | EsEmpresa]
    serializer_class = PermisoSerializer
    pagination_class = None
    queryset = Permiso.objects.all().order_by('codigo')


class ListaCrearRolBaseView(ListCreateAPIView):
    """T054: el SUPERADMIN crea y lista los roles base de la plataforma."""

    permission_classes = [EsSuperAdmin]
    serializer_class = RolBaseSerializer
    pagination_class = None
    queryset = RolBase.objects.all().order_by('nombre')

    def perform_create(self, serializer):
        rol = serializer.save()
        _log(self.request, 'CREAR_ROL_BASE', 'rol_base', rol.id)


class EliminarRolBaseView(APIView):
    permission_classes = [EsSuperAdmin]

    def delete(self, request, rol_id):
        rol = get_object_or_404(RolBase, id=rol_id)
        rol.delete()
        _log(request, 'ELIMINAR_ROL_BASE', 'rol_base', rol_id)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PermisoRolBaseView(APIView):
    """T055: asigna (POST) o quita (DELETE) un permiso del catálogo a un rol base."""

    permission_classes = [EsSuperAdmin]

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


class ListaCrearMisDireccionesView(ListCreateAPIView):
    """CU13: el comprador ve y agrega SUS direcciones de envío — con
    latitud/longitud puestas por GPS o clic en el mapa (Leaflet) del
    frontend, nunca escritas a mano."""

    permission_classes = [EsComprador]
    serializer_class = DireccionSerializer
    pagination_class = None

    def get_queryset(self):
        return Direccion.objects.filter(comprador__usuario=self.request.user, activo=True).order_by('-es_predeterminada', '-creado_en')

    def perform_create(self, serializer):
        comprador = get_object_or_404(Comprador, usuario=self.request.user)
        direccion = serializer.save(comprador=comprador)
        _log(self.request, 'CREAR_DIRECCION', 'direccion', direccion.id, detalle={'alias': direccion.alias})


class EditarEliminarMiDireccionView(APIView):
    """CU13: edita o elimina una de las direcciones del comprador
    autenticado — nunca la de otro comprador."""

    permission_classes = [EsComprador]

    def patch(self, request, direccion_id):
        direccion = get_object_or_404(Direccion, id=direccion_id, comprador__usuario=request.user)
        serializer = DireccionSerializer(direccion, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_DIRECCION', 'direccion', direccion.id, detalle={'alias': direccion.alias})
        return Response(DireccionSerializer(direccion).data)

    def delete(self, request, direccion_id):
        direccion = get_object_or_404(Direccion, id=direccion_id, comprador__usuario=request.user)
        alias = direccion.alias
        direccion.delete()
        _log(request, 'ELIMINAR_DIRECCION', 'direccion', direccion_id, detalle={'alias': alias})
        return Response(status=status.HTTP_204_NO_CONTENT)
