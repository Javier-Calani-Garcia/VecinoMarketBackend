from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.auditoria.models import LogAuditoria
from apps.core.utils import get_client_ip
from apps.usuarios.permissions import EsAdmin, TienePermisoEmpleado

from .models import MetodoPago
from .serializers import MetodoPagoAdminSerializer, MetodoPagoEmpresaSerializer


def _log(request, accion, entidad_id, detalle=None):
    LogAuditoria.objects.create(
        usuario=request.user,
        accion=accion,
        entidad_afectada='metodo_pago',
        entidad_id=entidad_id,
        detalle=detalle or {},
        ip_origen=get_client_ip(request),
    )


class ListaCrearMetodoPagoAdminView(generics.ListCreateAPIView):
    """CU25: el SuperAdmin/Admin ve y registra los métodos de pago de
    cualquier empresa (?empresa=<id> para filtrar a una en particular)."""

    permission_classes = [EsAdmin]
    serializer_class = MetodoPagoAdminSerializer
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = MetodoPago.objects.filter(activo=True).select_related('empresa').order_by('-predeterminado', '-creado_en')
        empresa_id = self.request.query_params.get('empresa')
        if empresa_id:
            qs = qs.filter(empresa_id=empresa_id)
        return qs

    def perform_create(self, serializer):
        metodo = serializer.save()
        _log(self.request, 'CREAR_METODO_PAGO', metodo.id, {'nombre': metodo.nombre, 'empresa_id': metodo.empresa_id})


class EditarEliminarMetodoPagoAdminView(APIView):
    """CU25: edita o elimina el método de pago de cualquier empresa."""

    permission_classes = [EsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, metodo_id):
        metodo = get_object_or_404(MetodoPago, id=metodo_id)
        serializer = MetodoPagoAdminSerializer(metodo, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_METODO_PAGO', metodo.id, {'nombre': metodo.nombre})
        return Response(MetodoPagoAdminSerializer(metodo, context={'request': request}).data)

    def delete(self, request, metodo_id):
        metodo = get_object_or_404(MetodoPago, id=metodo_id)
        nombre = metodo.nombre
        metodo.delete()
        _log(request, 'ELIMINAR_METODO_PAGO', metodo_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)


class ListaCrearMisMetodosPagoView(generics.ListCreateAPIView):
    """CU25: la empresa (el dueño, o un empleado con el permiso
    'gestionar_pagos') ve y registra SUS PROPIOS métodos de pago —
    'empresa' se fuerza a la del usuario autenticado, nunca la manda el
    cliente, para que un empleado no pueda tocar los de otra empresa."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pagos'
    serializer_class = MetodoPagoEmpresaSerializer
    pagination_class = None
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        return MetodoPago.objects.filter(
            activo=True, empresa=self.request.user.get_empresa()
        ).order_by('-predeterminado', '-creado_en')

    def perform_create(self, serializer):
        metodo = serializer.save(empresa=self.request.user.get_empresa())
        _log(self.request, 'CREAR_METODO_PAGO', metodo.id, {'nombre': metodo.nombre})


class EditarEliminarMiMetodoPagoView(APIView):
    """CU25: la empresa edita o elimina uno de SUS métodos de pago —
    get_object_or_404 filtra por su propia empresa, así que no puede
    tocar el de otra aunque adivine el id."""

    permission_classes = [TienePermisoEmpleado]
    permiso_requerido = 'gestionar_pagos'
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def patch(self, request, metodo_id):
        metodo = get_object_or_404(MetodoPago, id=metodo_id, empresa=request.user.get_empresa())
        serializer = MetodoPagoEmpresaSerializer(metodo, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _log(request, 'EDITAR_METODO_PAGO', metodo.id, {'nombre': metodo.nombre})
        return Response(MetodoPagoEmpresaSerializer(metodo, context={'request': request}).data)

    def delete(self, request, metodo_id):
        metodo = get_object_or_404(MetodoPago, id=metodo_id, empresa=request.user.get_empresa())
        nombre = metodo.nombre
        metodo.delete()
        _log(request, 'ELIMINAR_METODO_PAGO', metodo_id, {'nombre': nombre})
        return Response(status=status.HTTP_204_NO_CONTENT)
