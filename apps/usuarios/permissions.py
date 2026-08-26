from rest_framework.permissions import BasePermission


class EsAdmin(BasePermission):
    message = 'Solo el administrador de la plataforma puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.es_admin())


class EsEmpresa(BasePermission):
    message = 'Solo el dueño de la empresa puede realizar esta acción.'

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.es_empresa())


class TienePermisoEmpleado(BasePermission):
    """
    Permite el acceso si el usuario es dueño de la empresa (acceso total al
    tenant) o si es un empleado con el permiso puntual que exige la vista
    (view.permiso_requerido).
    """

    message = 'No tienes el permiso necesario para esta acción.'

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.es_empresa():
            return True
        codigo = getattr(view, 'permiso_requerido', None)
        if user.es_empleado() and codigo:
            empleado = getattr(user, 'empleado', None)
            return bool(empleado) and empleado.permisos.filter(permiso__codigo=codigo).exists()
        return False
