from django.contrib import admin

from .models import ProviderProfile


@admin.register(ProviderProfile)
class ProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'user_email',
        'service_category',
        'onboarding_status',
        'approval_status',
        'is_active',
        'created_at',
    )
    list_filter = ('service_category', 'onboarding_status', 'approval_status', 'is_active', 'created_at')
    search_fields = ('business_name', 'display_name', 'user__email', 'user__full_name', 'contact_phone')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'reviewed_at', 'reviewed_by')
    ordering = ('-created_at',)

    fieldsets = (
        ('Provider', {
            'fields': ('user', 'service_category', 'business_name', 'display_name', 'is_active'),
        }),
        ('Contact & Location', {
            'fields': (
                'contact_phone', 'contact_email', 'business_address', 'city', 'state',
                'postal_code', 'country', 'latitude', 'longitude',
            ),
        }),
        ('Review State', {
            'fields': (
                'onboarding_status', 'approval_status', 'submitted_at', 'reviewed_at',
                'reviewed_by', 'review_note',
            ),
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'
