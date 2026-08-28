from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Plan, Suscripcion


class PlanSerializer(serializers.ModelSerializer):
    """CU01/CU20: catálogo de planes activos que el admin puede asignar a una empresa."""

    class Meta:
        model = Plan
        fields = [
            'id', 'nombre', 'precio_mensual', 'limite_productos',
            'incluye_live_commerce', 'incluye_ia', 'porcentaje_comision', 'estado',
        ]
        read_only_fields = fields


class SuscripcionSerializer(serializers.ModelSerializer):
    plan_nombre = serializers.CharField(source='plan.nombre', read_only=True)

    class Meta:
        model = Suscripcion
        fields = [
            'id', 'empresa', 'plan', 'plan_nombre', 'fecha_inicio',
            'fecha_vencimiento', 'estado', 'renovacion_automatica',
        ]
        read_only_fields = fields


class AsignarPlanSerializer(serializers.Serializer):
    """CU01: el admin asigna (o renueva) el plan de una empresa, abriendo una
    nueva suscripción ACTIVA a partir de hoy. Sirve tanto para la primera
    asignación (empresa "solicitando suscripción") como para renovar una
    suscripción expirada."""

    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=Plan.objects.filter(estado=Plan.Estado.ACTIVO), source='plan'
    )
    dias = serializers.IntegerField(min_value=1, max_value=730, default=30, required=False)

    def save(self):
        empresa = self.context['empresa']
        plan = self.validated_data['plan']
        dias = self.validated_data.get('dias', 30)
        hoy = timezone.now().date()

        suscripcion = Suscripcion.objects.create(
            empresa=empresa,
            plan=plan,
            fecha_inicio=hoy,
            fecha_vencimiento=hoy + timedelta(days=dias),
        )
        empresa.plan = plan
        empresa.save(update_fields=['plan'])
        return suscripcion
