from django.contrib import admin

from .models import LogAuditoria


@admin.register(LogAuditoria)
class LogAuditoriaAdmin(admin.ModelAdmin):
    list_display = ('accion', 'usuario', 'empresa', 'objeto_id', 'ip', 'creado_en')
    list_filter = ('accion', 'empresa')
    search_fields = ('usuario__email', 'objeto_id')
    readonly_fields = [f.name for f in LogAuditoria._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
