from django.db import models

from apps.core.models import TenantModel


class Promocion(TenantModel):
    class Tipo(models.TextChoices):
        PORCENTAJE = 'PORCENTAJE', 'Porcentaje'
        MONTO_FIJO = 'MONTO_FIJO', 'Monto fijo'

    class Estado(models.TextChoices):
        ACTIVA = 'ACTIVA', 'Activa'
        FINALIZADA = 'FINALIZADA', 'Finalizada'
        CANCELADA = 'CANCELADA', 'Cancelada'

    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField()
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.ACTIVA)
    productos = models.ManyToManyField(
        'catalogo.Producto', through='PromocionProducto', related_name='promociones'
    )

    class Meta:
        verbose_name = 'Promoción'
        verbose_name_plural = 'Promociones'
        constraints = [
            models.CheckConstraint(check=models.Q(valor__gt=0), name='promocion_valor_gt_0'),
            models.CheckConstraint(
                check=models.Q(fecha_fin__gt=models.F('fecha_inicio')), name='promocion_fechas_validas'
            ),
        ]

    def __str__(self):
        return self.nombre


class PromocionProducto(models.Model):
    promocion = models.ForeignKey(Promocion, on_delete=models.CASCADE)
    producto = models.ForeignKey('catalogo.Producto', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Producto en promoción'
        verbose_name_plural = 'Productos en promoción'
        unique_together = ('promocion', 'producto')


class LiveCommerceSesion(TenantModel):
    class Estado(models.TextChoices):
        PROGRAMADA = 'PROGRAMADA', 'Programada'
        EN_VIVO = 'EN_VIVO', 'En vivo'
        FINALIZADA = 'FINALIZADA', 'Finalizada'

    titulo = models.CharField(max_length=150)
    url_stream = models.URLField(max_length=255, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PROGRAMADA)
    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    productos = models.ManyToManyField(
        'catalogo.Producto', through='LiveCommerceProducto', related_name='sesiones_live'
    )

    class Meta:
        verbose_name = 'Sesión de live commerce'
        verbose_name_plural = 'Sesiones de live commerce'

    def __str__(self):
        return self.titulo


class LiveCommerceProducto(models.Model):
    sesion = models.ForeignKey(LiveCommerceSesion, on_delete=models.CASCADE)
    producto = models.ForeignKey('catalogo.Producto', on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Producto en sesión live'
        verbose_name_plural = 'Productos en sesión live'
        unique_together = ('sesion', 'producto')
