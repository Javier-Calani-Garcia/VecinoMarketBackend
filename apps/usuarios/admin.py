from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import EmpleadoPermiso, Empresa, Permiso, Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    model = Usuario
    list_display = ('email', 'nombre', 'rol', 'empresa', 'is_active', 'is_staff')
    list_filter = ('rol', 'is_active', 'empresa')
    search_fields = ('email', 'nombre')
    ordering = ('email',)

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Datos personales', {'fields': ('nombre', 'rol', 'empresa', 'creado_por')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'nombre', 'rol', 'empresa', 'password1', 'password2'),
        }),
    )


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'rubro', 'slug', 'suscripcion_activa', 'creada_por')
    search_fields = ('nombre', 'slug')


@admin.register(Permiso)
class PermisoAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'descripcion')


@admin.register(EmpleadoPermiso)
class EmpleadoPermisoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'permiso')
