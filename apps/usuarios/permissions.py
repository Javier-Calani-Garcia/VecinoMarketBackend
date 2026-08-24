from rest_framework.permissions import BasePermission


class EsSuperAdmin(BasePermission):
    message = 'Solo el superadministrador puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.es_superadmin())


class EsAdminEmpresa(BasePermission):
    message = 'Solo el administrador de la empresa puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.es_admin_empresa())


class TienePermisoEmpleado(BasePermission):
    """
    Permite el acceso si el usuario es admin de su empresa (acceso total al
    tenant) o si es un empleado con el permiso puntual que exige la vista
    (view.permiso_requerido).
    """

    message = 'No tienes el permiso necesario para esta acción.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.es_admin_empresa():
            return True
        codigo = getattr(view, 'permiso_requerido', None)
        if user.es_empleado() and codigo:
            return user.permisos.filter(permiso__codigo=codigo, activo=True).exists()
        return False
