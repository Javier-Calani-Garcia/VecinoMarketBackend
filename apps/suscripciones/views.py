from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.models import Empresa
from apps.usuarios.permissions import EsSuperAdmin

from .models import Plan
from .serializers import EditarSuscripcionSerializer, PlanSerializer


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
