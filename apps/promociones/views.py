from django.db import DatabaseError, connection
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.models import Empresa
from apps.usuarios.permissions import EsAdmin, TienePermisoEmpleado

from .models import LiveCommerceSesion, Promocion
from .serializers import (
    LiveAdminSerializer,
    LiveEmpresaSerializer,
    LivePublicoSerializer,
    PromocionAdminSerializer,
    PromocionEmpresaSerializer,
)


def _log(request, accion, entidad_id, detalle=None, entidad_afectada='promocion'):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada=entidad_afectada,
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaResumenEmpresasPromocionesAdminView(APIView):
    """CU16: el SuperAdmin ve, por empresa, cuántas promociones activas y
    vigentes tiene, antes de entrar a ver el detalle."""

    permission_classes = [EsAdmin]

    def get(self, request):
        empresas = Empresa.objects.all().order_by('razon_social')
        q = request.query_params.get('q', '').strip()
        if q:
            empresas = empresas.filter(razon_social__icontains=q)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT empresa_id, COUNT(*)
                FROM promociones_promocion
                WHERE activo = true AND estado = 'ACTIVA' AND now() BETWEEN fecha_inicio AND fecha_fin
                GROUP BY empresa_id
            """)
            resumen = {row[0]: row[1] for row in cursor.fetchall()}

        resultados = [
            {
                'id': e.id, 'razon_social': e.razon_social, 'slug': e.slug,
                'logo_url': e.logo_url, 'ciudad': e.ciudad,
                'promociones_activas': resumen.get(e.id, 0),
            }
            for e in empresas
        ]
        return Response(resultados)


class ListaPromocionesAdminView(generics.ListAPIView):
    """CU16: el SuperAdmin/Admin ve las promociones de una empresa
    (?empresa=<id>) o de todas."""

    permission_classes = [EsAdmin]
    serializer_class = PromocionAdminSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Promocion.objects.filter(activo=True).select_related('empresa').prefetch_related('productos').order_by('-fecha_inicio')
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


class EditarEliminarPromocionAdminView(APIView):
    """CU16: edita o elimina la promoción de cualquier empresa."""

    permission_classes = [EsAdmin]

    def patch(self, request, promocion_id):
        promocion = get_object_or_404(Promocion, id=promocion_id)
        serializer = PromocionAdminSerializer(promocion, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_PROMOCION', promocion.id, {'nombre': promocion.nombre})
        return Response(PromocionAdminSerializer(promocion).data)

    def delete(self, request, promocion_id):
        promocion = get_object_or_404(Promocion, id=promocion_id)
        nombre = promocion.nombre
        promocion.delete()
        _log(request, 'ELIMINAR_PROMOCION', promocion_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaCrearMisPromocionesView(generics.ListCreateAPIView):
    """CU16: la empresa (dueño o empleado con permiso 'gestionar_promociones')
    ve y crea SUS PROPIAS promociones."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_promociones'
    serializer_class = PromocionEmpresaSerializer
    pagination_class = None

    def get_queryset(self):
        return Promocion.objects.filter(
            activo=True, empresa=self.request.user.get_empresa()
        ).prefetch_related('productos').order_by('-fecha_inicio')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'empresa': self.request.user.get_empresa()}

    def perform_create(self, serializer):
        promocion = serializer.save(empresa=self.request.user.get_empresa())
        _log(self.request, 'CREAR_PROMOCION', promocion.id, {'nombre': promocion.nombre})


class EditarEliminarMiPromocionView(APIView):
    """CU16: la empresa edita o elimina una de SUS promociones."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_promociones'

    def patch(self, request, promocion_id):
        promocion = get_object_or_404(Promocion, id=promocion_id, empresa=request.user.get_empresa())
        serializer = PromocionEmpresaSerializer(
            promocion, data=request.data, partial=True, context={'empresa': request.user.get_empresa()}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_PROMOCION', promocion.id, {'nombre': promocion.nombre})
        return Response(PromocionEmpresaSerializer(promocion).data)

    def delete(self, request, promocion_id):
        promocion = get_object_or_404(Promocion, id=promocion_id, empresa=request.user.get_empresa())
        nombre = promocion.nombre
        promocion.delete()
        _log(request, 'ELIMINAR_PROMOCION', promocion_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaLivesPublicoView(generics.ListAPIView):
    """CU17: lo que ve cualquier visitante desde el botón "LIVE" — las
    sesiones EN_VIVO ahora mismo, con qué empresa y qué productos."""

    permission_classes = [AllowAny]
    serializer_class = LivePublicoSerializer
    pagination_class = None

    def get_queryset(self):
        return LiveCommerceSesion.objects.filter(
            activo=True, estado=LiveCommerceSesion.Estado.EN_VIVO
        ).select_related('empresa').prefetch_related('productos')


class ListaCrearMisLivesView(generics.ListCreateAPIView):
    """CU17: la empresa (dueño o empleado con permiso 'gestionar_promociones')
    programa y emite sus propias sesiones de live commerce."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_promociones'
    serializer_class = LiveEmpresaSerializer
    pagination_class = None

    def get_queryset(self):
        return LiveCommerceSesion.objects.filter(
            activo=True, empresa=self.request.user.get_empresa()
        ).prefetch_related('productos').order_by('-fecha_inicio')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'empresa': self.request.user.get_empresa()}

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sesion = serializer.save(empresa=request.user.get_empresa())
        except DatabaseError as exc:
            return Response({'detail': str(exc).split('\n')[0]}, status=status.HTTP_400_BAD_REQUEST)
        _log(request, 'CREAR_LIVE', sesion.id, {'titulo': sesion.titulo}, entidad_afectada='live')
        return Response(LiveEmpresaSerializer(sesion).data, status=status.HTTP_201_CREATED)


class EditarEliminarMiLiveView(APIView):
    """CU17: la empresa edita (incluido pasar a EN_VIVO o FINALIZADA) o
    elimina una de SUS sesiones. Pasar a EN_VIVO falla si la empresa tiene
    una sanción activa (trg_verificar_bloqueo_live)."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_promociones'

    def patch(self, request, live_id):
        sesion = get_object_or_404(LiveCommerceSesion, id=live_id, empresa=request.user.get_empresa())
        serializer = LiveEmpresaSerializer(
            sesion, data=request.data, partial=True, context={'empresa': request.user.get_empresa()}
        )
        serializer.is_valid(raise_exception=True)
        try:
            serializer.save()
        except DatabaseError as exc:
            return Response({'detail': str(exc).split('\n')[0]}, status=status.HTTP_400_BAD_REQUEST)
        _log(request, 'EDITAR_LIVE', sesion.id, {'estado': sesion.estado}, entidad_afectada='live')
        return Response(LiveEmpresaSerializer(sesion).data)

    def delete(self, request, live_id):
        sesion = get_object_or_404(LiveCommerceSesion, id=live_id, empresa=request.user.get_empresa())
        titulo = sesion.titulo
        sesion.delete()
        _log(request, 'ELIMINAR_LIVE', live_id, {'titulo': titulo}, entidad_afectada='live')
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaLivesAdminView(generics.ListAPIView):
    """CU17: el SuperAdmin/Admin ve todas las sesiones (?empresa=<id>,
    ?estado=EN_VIVO) — para el panel de soporte."""

    permission_classes = [EsAdmin]
    serializer_class = LiveAdminSerializer
    pagination_class = None

    def get_queryset(self):
        qs = LiveCommerceSesion.objects.filter(activo=True).select_related('empresa').prefetch_related('productos').order_by('-fecha_inicio')
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


class DarDeBajaLiveAdminView(APIView):
    """CU17: el SuperAdmin corta cualquier live (lo pasa a FINALIZADA),
    por ejemplo por incumplimiento de las normas de servicio."""

    permission_classes = [EsAdmin]

    def post(self, request, live_id):
        sesion = get_object_or_404(LiveCommerceSesion, id=live_id)
        sesion.estado = LiveCommerceSesion.Estado.FINALIZADA
        sesion.fecha_fin = timezone.now()
        sesion.save(update_fields=['estado', 'fecha_fin'])
        _log(request, 'DAR_DE_BAJA_LIVE', sesion.id, {'titulo': sesion.titulo, 'empresa_id': sesion.empresa_id}, entidad_afectada='live')
        return Response(LiveAdminSerializer(sesion).data)


class BloquearEmpresaLiveAdminView(APIView):
    """CU17: sanciona a una empresa por incumplimiento — le impide emitir
    en vivo por N días (trg_verificar_bloqueo_live hace cumplir esto a
    nivel de base de datos, no solo en la vista)."""

    permission_classes = [EsAdmin]

    def post(self, request, empresa_id):
        try:
            dias = int(request.data.get('dias'))
        except (TypeError, ValueError):
            return Response({'detail': 'dias debe ser un número entero positivo.'}, status=status.HTTP_400_BAD_REQUEST)
        if dias <= 0:
            return Response({'detail': 'dias debe ser un número entero positivo.'}, status=status.HTTP_400_BAD_REQUEST)

        empresa = get_object_or_404(Empresa, id=empresa_id)
        empresa.bloqueo_live_hasta = timezone.now() + timezone.timedelta(days=dias)
        empresa.save(update_fields=['bloqueo_live_hasta'])

        LiveCommerceSesion.objects.filter(empresa=empresa, estado=LiveCommerceSesion.Estado.EN_VIVO).update(
            estado=LiveCommerceSesion.Estado.FINALIZADA, fecha_fin=timezone.now()
        )

        _log(request, 'BLOQUEAR_LIVE_EMPRESA', empresa.id, {'dias': dias, 'hasta': str(empresa.bloqueo_live_hasta)}, entidad_afectada='empresa')
        return Response({'empresa': empresa.id, 'bloqueo_live_hasta': empresa.bloqueo_live_hasta})
