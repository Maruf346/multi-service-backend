from rest_framework.permissions import BasePermission


class IsSuperAdmin(BasePermission):
    """Allow access only to SUPER_ADMIN users."""

    message = 'You must be a Super Admin to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_super_admin
        )


class IsSuperAdminOrReadOnly(BasePermission):
    """
    Allow Super Admins full CRUD.
    Allow authenticated Restaurant Admins read-only access.
    """

    message = 'Write access requires Super Admin privileges.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        # Safe methods available to all authenticated users
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return True
        return request.user.is_super_admin

