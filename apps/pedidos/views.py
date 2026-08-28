from django.db import connection
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.permissions import EsAdmin, EsComprador, TienePermisoEmpleado

from .models import Carrito, Entrega, OrdenCompra, Pedido
from .serializers import CarritoDetalleAdminSerializer, EntregaSerializer, PedidoSerializer


def _log(request, accion, entidad_id, detalle=None, entidad_afectada='pedido'):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada=entidad_afectada,
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaCarritosAdminView(APIView):
    """CU11: el SuperAdmin/Admin ve, en vivo (el frontend re-consulta cada
    pocos segundos), qué está agregando cada comprador a su carrito. Es de
    solo lectura — el único que puede modificar un carrito es el propio
    comprador, desde su sesión de compra."""

    permission_classes = [EsAdmin]

    def get(self, request):
        qs = Carrito.objects.select_related('comprador__usuario').order_by('-actualizado_en')

        estado = request.query_params.get('estado', Carrito.Estado.ABIERTO)
        if estado:
            qs = qs.filter(estado=estado)

        q = request.query_params.get('q', '').strip()
        if q:
            qs = qs.filter(Q(comprador__usuario__nombre__icontains=q) | Q(comprador__usuario__email__icontains=q))

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT carrito_id, COALESCE(SUM(cantidad), 0), COALESCE(SUM(cantidad * precio_unitario), 0)
                FROM pedidos_carritoitem
                GROUP BY carrito_id
            """)
            resumen = {row[0]: {'total_items': row[1], 'total_monto': row[2]} for row in cursor.fetchall()}

        vacio = {'total_items': 0, 'total_monto': 0}
        resultados = [
            {
                'id': c.id,
                'comprador': c.comprador_id,
                'comprador_nombre': c.comprador.usuario.nombre,
                'comprador_email': c.comprador.usuario.email,
                'estado': c.estado,
                'creado_en': c.creado_en,
                'actualizado_en': c.actualizado_en,
                **resumen.get(c.id, vacio),
            }
            for c in qs
        ]
        return Response(resultados)


class DetalleCarritoAdminView(generics.RetrieveAPIView):
    """CU11: detalle de un carrito (sus ítems) — solo lectura."""

    permission_classes = [EsAdmin]
    serializer_class = CarritoDetalleAdminSerializer
    queryset = Carrito.objects.select_related('comprador__usuario').prefetch_related('items__producto')


class PedidoPagination(PageNumberPagination):
    page_size = 30
    page_size_query_param = 'page_size'
    max_page_size = 100


def _pedidos_queryset():
    return (
        Pedido.objects.select_related('empresa', 'orden_compra__comprador__usuario')
        .prefetch_related('items__producto')
        .order_by('-creado_en')
    )


def _filtrar_pedidos(qs, params):
    """CU12: 'tipo=pedido' (estado_pago PENDIENTE) vs 'tipo=venta'
    (estado_pago PAGADO) — el criterio que separa los dos dashboards."""
    tipo = params.get('tipo')
    if tipo == 'pedido':
        qs = qs.filter(orden_compra__estado_pago=OrdenCompra.EstadoPago.PENDIENTE)
    elif tipo == 'venta':
        qs = qs.filter(orden_compra__estado_pago=OrdenCompra.EstadoPago.PAGADO)

    estado = params.get('estado')
    if estado:
        qs = qs.filter(estado=estado)

    metodo_pago = params.get('metodo_pago')
    if metodo_pago:
        qs = qs.filter(orden_compra__metodo_pago=metodo_pago)

    q = params.get('q', '').strip()
    if q:
        qs = qs.filter(Q(numero_pedido__icontains=q) | Q(orden_compra__comprador__usuario__nombre__icontains=q))

    return qs


def _aplicar_cambios_pedido(request, pedido):
    """Escribe estado (Pedido, ciclo de vida operativo) y/o estado_pago
    (OrdenCompra, lo que decide si es "Pedido" o "Venta") — ambos opcionales
    e independientes entre sí en el mismo PATCH."""
    nuevo_estado = request.data.get('estado')
    if nuevo_estado:
        if nuevo_estado not in Pedido.Estado.values:
            raise ValueError('Estado de pedido inválido.')
        pedido.estado = nuevo_estado
        pedido.save(update_fields=['estado'])

    nuevo_estado_pago = request.data.get('estado_pago')
    if nuevo_estado_pago:
        if nuevo_estado_pago not in OrdenCompra.EstadoPago.values:
            raise ValueError('Estado de pago inválido.')
        pedido.orden_compra.estado_pago = nuevo_estado_pago
        pedido.orden_compra.save(update_fields=['estado_pago'])


class ListaPedidosAdminView(generics.ListAPIView):
    """CU12: el SuperAdmin/Admin ve los pedidos/ventas de TODAS las
    empresas — ?empresa=<id> para filtrar a una en particular, ?tipo=
    pedido|venta para el dashboard correspondiente."""

    permission_classes = [EsAdmin]
    serializer_class = PedidoSerializer
    pagination_class = PedidoPagination

    def get_queryset(self):
        qs = _filtrar_pedidos(_pedidos_queryset(), self.request.query_params)
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        return qs


class EditarEliminarPedidoAdminView(APIView):
    """CU12: edita (estado del pedido y/o estado de pago) o elimina
    cualquier pedido/venta."""

    permission_classes = [EsAdmin]

    def patch(self, request, pedido_id):
        pedido = get_object_or_404(Pedido.objects.select_related('orden_compra'), id=pedido_id)
        try:
            _aplicar_cambios_pedido(request, pedido)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _log(request, 'EDITAR_PEDIDO', pedido.id, {'numero_pedido': pedido.numero_pedido, 'estado': pedido.estado})
        return Response(PedidoSerializer(pedido).data)

    def delete(self, request, pedido_id):
        pedido = get_object_or_404(Pedido, id=pedido_id)
        numero = pedido.numero_pedido
        pedido.delete()
        _log(request, 'ELIMINAR_PEDIDO', pedido_id, {'numero_pedido': numero})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaMisPedidosView(generics.ListAPIView):
    """CU12: la empresa (dueño o empleado con permiso 'gestionar_pedidos')
    ve SUS PROPIOS pedidos/ventas."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pedidos'
    serializer_class = PedidoSerializer
    pagination_class = PedidoPagination

    def get_queryset(self):
        qs = _pedidos_queryset().filter(empresa=self.request.user.get_empresa())
        return _filtrar_pedidos(qs, self.request.query_params)


class EditarEliminarMiPedidoView(APIView):
    """CU12: la empresa edita o elimina uno de SUS pedidos/ventas —
    get_object_or_404 filtra por su propia empresa."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pedidos'

    def patch(self, request, pedido_id):
        pedido = get_object_or_404(
            Pedido.objects.select_related('orden_compra'), id=pedido_id, empresa=request.user.get_empresa()
        )
        try:
            _aplicar_cambios_pedido(request, pedido)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        _log(request, 'EDITAR_PEDIDO', pedido.id, {'numero_pedido': pedido.numero_pedido, 'estado': pedido.estado})
        return Response(PedidoSerializer(pedido).data)

    def delete(self, request, pedido_id):
        pedido = get_object_or_404(Pedido, id=pedido_id, empresa=request.user.get_empresa())
        numero = pedido.numero_pedido
        pedido.delete()
        _log(request, 'ELIMINAR_PEDIDO', pedido_id, {'numero_pedido': numero})
        return Response(status=status.HTTP_204_NO_CONTENT)


def _entregas_queryset():
    return Entrega.objects.select_related(
        'pedido__empresa', 'pedido__direccion_envio', 'pedido__sucursal_recojo',
        'pedido__orden_compra__comprador__usuario',
    ).order_by('-id')


def _marcar_entregada(entrega):
    with connection.cursor() as cursor:
        cursor.execute('SELECT fn_marcar_entregada(%s)', [entrega.pedido_id])
    entrega.refresh_from_db()


class ListaEntregasAdminView(generics.ListAPIView):
    """CU13: el SuperAdmin/Admin ve las entregas de TODAS las empresas —
    solo de pedidos ya pagados (una Entrega nace junto con su Pedido, pero
    solo importa el envío una vez que el pago está confirmado)."""

    permission_classes = [EsAdmin]
    serializer_class = EntregaSerializer
    pagination_class = PedidoPagination

    def get_queryset(self):
        qs = _entregas_queryset().filter(pedido__orden_compra__estado_pago=OrdenCompra.EstadoPago.PAGADO)
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(pedido__empresa_id=empresa_id)
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


class EditarEliminarEntregaAdminView(APIView):
    """CU13: edita (estado/fecha) o elimina la entrega de cualquier pedido."""

    permission_classes = [EsAdmin]

    def patch(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id)
        serializer = EntregaSerializer(entrega, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_ENTREGA', entrega.id, {'numero_pedido': entrega.pedido.numero_pedido, 'estado': entrega.estado}, entidad_afectada='entrega')
        return Response(EntregaSerializer(entrega).data)

    def delete(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id)
        numero = entrega.pedido.numero_pedido
        entrega.delete()
        _log(request, 'ELIMINAR_ENTREGA', entrega_id, {'numero_pedido': numero}, entidad_afectada='entrega')
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarcarEntregadaAdminView(APIView):
    """CU13: atajo que marca la entrega ENTREGADA y, en la misma
    transacción (vía fn_marcar_entregada), el pedido como ENTREGADO —
    disparando la comisión de venta automática (CU26)."""

    permission_classes = [EsAdmin]

    def post(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id)
        _marcar_entregada(entrega)
        _log(request, 'MARCAR_ENTREGADA', entrega.id, {'numero_pedido': entrega.pedido.numero_pedido}, entidad_afectada='entrega')
        return Response(EntregaSerializer(entrega).data)


class ListaMisEntregasView(generics.ListAPIView):
    """CU13: la empresa (dueño o empleado con permiso 'gestionar_pedidos')
    ve las entregas de SUS PROPIOS pedidos pagados."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pedidos'
    serializer_class = EntregaSerializer
    pagination_class = PedidoPagination

    def get_queryset(self):
        qs = _entregas_queryset().filter(
            pedido__empresa=self.request.user.get_empresa(),
            pedido__orden_compra__estado_pago=OrdenCompra.EstadoPago.PAGADO,
        )
        estado = self.request.query_params.get('estado')
        if estado:
            qs = qs.filter(estado=estado)
        return qs


class EditarEliminarMiEntregaView(APIView):
    """CU13: la empresa edita o elimina la entrega de uno de SUS pedidos."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pedidos'

    def patch(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id, pedido__empresa=request.user.get_empresa())
        serializer = EntregaSerializer(entrega, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_ENTREGA', entrega.id, {'numero_pedido': entrega.pedido.numero_pedido, 'estado': entrega.estado}, entidad_afectada='entrega')
        return Response(EntregaSerializer(entrega).data)

    def delete(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id, pedido__empresa=request.user.get_empresa())
        numero = entrega.pedido.numero_pedido
        entrega.delete()
        _log(request, 'ELIMINAR_ENTREGA', entrega_id, {'numero_pedido': numero}, entidad_afectada='entrega')
        return Response(status=status.HTTP_204_NO_CONTENT)


class MarcarMiEntregaEntregadaView(APIView):
    """CU13: la empresa marca la entrega de uno de SUS pedidos como
    ENTREGADA (ver MarcarEntregadaAdminView)."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pedidos'

    def post(self, request, entrega_id):
        entrega = get_object_or_404(Entrega, id=entrega_id, pedido__empresa=request.user.get_empresa())
        _marcar_entregada(entrega)
        _log(request, 'MARCAR_ENTREGADA', entrega.id, {'numero_pedido': entrega.pedido.numero_pedido}, entidad_afectada='entrega')
        return Response(EntregaSerializer(entrega).data)


class ListaMisComprasView(generics.ListAPIView):
    """CU26: el comprador ve (y desde el frontend puede imprimir/exportar)
    sus propios recibos de compra pagada — solo lectura, no puede editar
    ni eliminar (eso es exclusivo de SuperAdmin/empresa, ver CU12)."""

    permission_classes = [EsComprador]
    serializer_class = PedidoSerializer
    pagination_class = PedidoPagination

    def get_queryset(self):
        return _pedidos_queryset().filter(
            orden_compra__comprador__usuario=self.request.user,
            orden_compra__estado_pago=OrdenCompra.EstadoPago.PAGADO,
        )
