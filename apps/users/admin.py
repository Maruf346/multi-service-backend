from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('email', 'full_name', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    search_fields = ('email', 'full_name', 'username', 'phone_number')
    ordering = ('email',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = UserAdmin.fieldsets + (
        ('Platform Role & Security', {
            'fields': ('role',),
        }),
        ('Profile', {
            'fields': (
                'full_name', 'phone_number', 'profile_image', 'street_address',
                'city', 'state', 'postal_code', 'country', 'latitude', 'longitude',
                'created_at', 'updated_at',
            ),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Platform Role & Security', {
            'fields': ('role',),
        }),
        ('Profile', {
            'fields': ('email', 'full_name', 'phone_number'),
        }),
    )
