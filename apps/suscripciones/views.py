from django.db import connection
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.models import Empresa
from apps.usuarios.permissions import EsSuperAdmin

from .models import Plan
from .serializers import EditarSuscripcionSerializer, PlanAdminSerializer, PlanSerializer


def _log(request, accion, entidad_id, detalle=None):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada='plan',
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaCrearPlanAdminView(ListCreateAPIView):
    """CU20: el SuperAdmin ve TODOS los planes (activos e inactivos) y crea
    planes nuevos."""

    permission_classes = [EsSuperAdmin]
    serializer_class = PlanAdminSerializer
    pagination_class = None
    queryset = Plan.objects.all().order_by('precio_mensual')

    def perform_create(self, serializer):
        plan = serializer.save()
        _log(self.request, 'CREAR_PLAN', plan.id, {'nombre': plan.nombre})


class EditarEliminarPlanAdminView(APIView):
    """CU20: edita un plan, o lo elimina — si alguna empresa ya tuvo una
    suscripción con ese plan (Suscripcion.plan usa on_delete=PROTECT, no se
    puede borrar sin perder ese historial), se rechaza con un mensaje claro
    en vez de un 500; la salida ahí es desactivarlo (estado=INACTIVO), no
    eliminarlo."""

    permission_classes = [EsSuperAdmin]

    def patch(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        serializer = PlanAdminSerializer(plan, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_PLAN', plan.id, {'nombre': plan.nombre, 'estado': plan.estado})
        return Response(PlanAdminSerializer(plan).data)

    def delete(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        nombre = plan.nombre
        try:
            plan.delete()
        except ProtectedError:
            return Response(
                {'detail': 'Este plan ya tiene empresas suscritas (activas o pasadas); no se puede eliminar. Desactívalo en vez de eso.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _log(request, 'ELIMINAR_PLAN', plan_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaPlanesView(ListAPIView):
    """CU01/CU20: planes activos disponibles para asignar a una empresa."""

    permission_classes = [EsSuperAdmin]
    serializer_class = PlanSerializer
    queryset = Plan.objects.filter(estado=Plan.Estado.ACTIVO).order_by('precio_mensual')


class EditarSuscripcionEmpresaView(APIView):
    """CU01: asigna o edita la suscripción vigente de una empresa (plan y
    fecha de vencimiento exacta)."""

    permission_classes = [EsSuperAdmin]

    def post(self, request, empresa_id):
        empresa = get_object_or_404(Empresa, id=empresa_id)
        serializer = EditarSuscripcionSerializer(data=request.data, context={'empresa': empresa})
        serializer.is_valid(raise_exception=True)
        suscripcion = serializer.save()

        LogAuditoria.objects.create(
            usuario=request.user,
            accion='EDITAR_SUSCRIPCION_EMPRESA',
            entidad_afectada='empresa',
            entidad_id=empresa.id,
            detalle={
                'plan': suscripcion.plan.nombre,
                'fecha_vencimiento': str(suscripcion.fecha_vencimiento),
            },
            ip_origen=get_client_ip(request),
        )
        return Response(
            {'detail': 'Suscripción actualizada.', 'fecha_vencimiento': suscripcion.fecha_vencimiento}
        )


class ExpirarSuscripcionesView(APIView):
    """CU01: dispara manualmente sp_expirar_suscripciones_vencidas (lo mismo
    que corre el comando `expirar_suscripciones` y cada vez que el admin abre
    el listado de empresas), por si se quiere forzar el refresco desde la UI."""

    permission_classes = [EsSuperAdmin]

    def post(self, request):
        with connection.cursor() as cursor:
            cursor.execute('CALL sp_expirar_suscripciones_vencidas();')
        return Response({'detail': 'Suscripciones vencidas actualizadas.'})
