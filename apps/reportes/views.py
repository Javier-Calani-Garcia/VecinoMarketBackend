from django.db import connection
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.pedidos.models import Pedido
from apps.usuarios.models import Comprador, Empresa
from apps.usuarios.permissions import EsAdmin, EsComprador, TienePermisoEmpleado

from .models import Valoracion
from .serializers import ValoracionSerializer


def _log(request, accion, entidad_id, detalle=None):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada='valoracion',
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaCrearMisValoracionesView(generics.ListCreateAPIView):
    """CU04: el comprador ve y crea SUS valoraciones — solo puede calificar
    un pedido propio ya ENTREGADO, y solo una vez (OneToOne pedido<->
    valoracion; el segundo intento cae en el 400 de abajo)."""

    permission_classes = [EsComprador]
    serializer_class = ValoracionSerializer
    pagination_class = None

    def get_queryset(self):
        return Valoracion.objects.filter(comprador__usuario=self.request.user, activo=True).order_by('-creado_en')

    def create(self, request, *args, **kwargs):
        pedido_id = request.data.get('pedido')
        pedido = get_object_or_404(
            Pedido.objects.select_related('empresa', 'orden_compra__comprador'),
            id=pedido_id, orden_compra__comprador__usuario=request.user,
        )
        if pedido.estado != Pedido.Estado.ENTREGADO:
            return Response({'detail': 'Solo puedes calificar pedidos ya entregados.'}, status=status.HTTP_400_BAD_REQUEST)
        if Valoracion.objects.filter(pedido=pedido).exists():
            return Response({'detail': 'Ya calificaste este pedido.'}, status=status.HTTP_400_BAD_REQUEST)

        comprador = get_object_or_404(Comprador, usuario=request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valoracion = serializer.save(pedido=pedido, comprador=comprador, empresa=pedido.empresa)
        _log(request, 'CREAR_VALORACION', valoracion.id, {'empresa_id': valoracion.empresa_id, 'calificacion': valoracion.calificacion})
        return Response(ValoracionSerializer(valoracion).data, status=status.HTTP_201_CREATED)


class EditarEliminarMiValoracionView(APIView):
    """CU04: el comprador edita o elimina una de SUS valoraciones."""

    permission_classes = [EsComprador]

    def patch(self, request, valoracion_id):
        valoracion = get_object_or_404(Valoracion, id=valoracion_id, comprador__usuario=request.user)
        serializer = ValoracionSerializer(valoracion, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_VALORACION', valoracion.id, {'calificacion': valoracion.calificacion})
        return Response(ValoracionSerializer(valoracion).data)

    def delete(self, request, valoracion_id):
        valoracion = get_object_or_404(Valoracion, id=valoracion_id, comprador__usuario=request.user)
        valoracion.delete()
        _log(request, 'ELIMINAR_VALORACION', valoracion_id, {})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaValoracionesEmpresaView(generics.ListAPIView):
    """CU04: la empresa (dueño o empleado con permiso 'ver_reportes') ve
    las valoraciones que recibió — de solo lectura, no puede editar ni
    eliminar (eso es del comprador que la escribió, o del SuperAdmin para
    moderar)."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'ver_reportes'
    serializer_class = ValoracionSerializer
    pagination_class = None

    def get_queryset(self):
        return Valoracion.objects.filter(
            empresa=self.request.user.get_empresa(), activo=True
        ).select_related('comprador__usuario', 'pedido').order_by('-creado_en')


class ListaResumenEmpresasValoracionesAdminView(APIView):
    """CU04: el SuperAdmin ve, por empresa, su ponderación global en
    estrellas y cuántas reseñas tiene, antes de entrar a leer los
    comentarios de una en particular."""

    permission_classes = [EsAdmin]

    def get(self, request):
        empresas = Empresa.objects.all().order_by('razon_social')
        q = request.query_params.get('q', '').strip()
        if q:
            empresas = empresas.filter(razon_social__icontains=q)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT empresa_id, ROUND(AVG(calificacion)::numeric, 2), COUNT(*)
                FROM reportes_valoracion
                WHERE activo = true
                GROUP BY empresa_id
            """)
            resumen = {row[0]: {'promedio': float(row[1]), 'total': row[2]} for row in cursor.fetchall()}

        vacio = {'promedio': 0, 'total': 0}
        resultados = [
            {
                'id': e.id, 'razon_social': e.razon_social, 'slug': e.slug,
                'logo_url': e.logo_url, 'ciudad': e.ciudad,
                **resumen.get(e.id, vacio),
            }
            for e in empresas
        ]
        return Response(resultados)


class ListaValoracionesAdminView(generics.ListAPIView):
    """CU04: el SuperAdmin ve los comentarios de una empresa (?empresa=<id>)
    — de solo lectura salvo por la eliminación (moderación de reseñas
    falsas u ofensivas), ver EliminarValoracionAdminView."""

    permission_classes = [EsAdmin]
    serializer_class = ValoracionSerializer
    pagination_class = None

    def get_queryset(self):
        qs = Valoracion.objects.filter(activo=True).select_related('comprador__usuario', 'empresa', 'pedido').order_by('-creado_en')
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        return qs


class EliminarValoracionAdminView(APIView):
    """CU04: el SuperAdmin elimina (modera) una reseña — no la edita, para
    no falsificar lo que escribió el comprador."""

    permission_classes = [EsAdmin]

    def delete(self, request, valoracion_id):
        valoracion = get_object_or_404(Valoracion, id=valoracion_id)
        _log(request, 'MODERAR_VALORACION', valoracion_id, {'empresa_id': valoracion.empresa_id})
        valoracion.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
