from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import UserRole


class IsSuperAdmin(BasePermission):
    message = 'You must be a Super Admin to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_super_admin
        )


class IsServiceProvider(BasePermission):
    message = 'You must be a service provider to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.SERVICE_PROVIDER
        )


class IsCustomer(BasePermission):
    message = 'You must be a customer to perform this action.'

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.role == UserRole.CUSTOMER
        )


class IsSuperAdminOrReadOnly(BasePermission):
    message = 'Write access requires Super Admin privileges.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_super_admin
