from django.db import models

from apps.core.models import BaseModel


class Plan(BaseModel):
    """CU20: catálogo de planes que vende el administrador."""

    class Estado(models.TextChoices):
        ACTIVO = 'ACTIVO', 'Activo'
        INACTIVO = 'INACTIVO', 'Inactivo'

    nombre = models.CharField(max_length=50)
    precio_mensual = models.DecimalField(max_digits=10, decimal_places=2)
    limite_productos = models.PositiveIntegerField(null=True, blank=True)  # NULL = ilimitado
    incluye_live_commerce = models.BooleanField(default=False)
    incluye_ia = models.BooleanField(default=False)
    porcentaje_comision = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVO)

    class Meta:
        verbose_name = 'Plan'
        verbose_name_plural = 'Planes'
        constraints = [
            models.CheckConstraint(check=models.Q(precio_mensual__gte=0), name='plan_precio_mensual_gte_0'),
        ]

    def __str__(self):
        return self.nombre


class Suscripcion(BaseModel):
    class Estado(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        VENCIDA = 'VENCIDA', 'Vencida'
        SUSPENDIDA = 'SUSPENDIDA', 'Suspendida'
        CANCELADA = 'CANCELADA', 'Cancelada'

    empresa = models.ForeignKey('usuarios.Empresa', on_delete=models.CASCADE, related_name='suscripciones')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='suscripciones')
    fecha_inicio = models.DateField()
    fecha_vencimiento = models.DateField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVA)
    renovacion_automatica = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Suscripción'
        verbose_name_plural = 'Suscripciones'
        indexes = [
            models.Index(fields=['empresa']),
            models.Index(fields=['fecha_vencimiento']),
        ]

    def __str__(self):
        return f'{self.empresa} - {self.plan} ({self.estado})'
