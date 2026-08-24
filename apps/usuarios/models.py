from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import BaseModel
from .managers import UsuarioManager


class Empresa(BaseModel):
    """Un tenant: el negocio/emprendimiento dentro del marketplace."""

    nombre = models.CharField(max_length=150)
    rubro = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    descripcion = models.TextField(blank=True)
    suscripcion_activa = models.BooleanField(default=True)
    creada_por = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.PROTECT,
        related_name='empresas_creadas',
        limit_choices_to={'rol': 'SUPERADMIN'},
    )

    class Meta:
        verbose_name = 'Empresa'
        verbose_name_plural = 'Empresas'

    def __str__(self):
        return self.nombre


class Usuario(AbstractBaseUser, PermissionsMixin):
    class Rol(models.TextChoices):
        SUPERADMIN = 'SUPERADMIN', 'Superadministrador'
        ADMIN_EMPRESA = 'ADMIN_EMPRESA', 'Administrador de empresa'
        EMPLEADO = 'EMPLEADO', 'Empleado'
        CLIENTE = 'CLIENTE', 'Cliente'

    email = models.EmailField(unique=True)
    nombre = models.CharField(max_length=150)
    rol = models.CharField(max_length=20, choices=Rol.choices)

    # Null para SUPERADMIN y CLIENTE: no pertenecen a un tenant.
    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='usuarios',
    )
    creado_por = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='usuarios_creados',
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    objects = UsuarioManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']

    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return f'{self.nombre} ({self.get_rol_display()})'

    def es_superadmin(self):
        return self.rol == self.Rol.SUPERADMIN

    def es_admin_empresa(self):
        return self.rol == self.Rol.ADMIN_EMPRESA

    def es_empleado(self):
        return self.rol == self.Rol.EMPLEADO

    def es_cliente(self):
        return self.rol == self.Rol.CLIENTE


class Permiso(BaseModel):
    """Catálogo de permisos base que un admin de empresa asigna a sus empleados."""

    codigo = models.CharField(max_length=50, unique=True)
    descripcion = models.CharField(max_length=200)

    class Meta:
        verbose_name = 'Permiso'
        verbose_name_plural = 'Permisos'

    def __str__(self):
        return self.codigo


class EmpleadoPermiso(BaseModel):
    """Relación empleado-permiso, dentro del contexto de su empresa."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='permisos')
    permiso = models.ForeignKey(Permiso, on_delete=models.CASCADE)

    class Meta:
        verbose_name = 'Permiso de empleado'
        verbose_name_plural = 'Permisos de empleados'
        unique_together = ('usuario', 'permiso')

    def __str__(self):
        return f'{self.usuario.email} -> {self.permiso.codigo}'
