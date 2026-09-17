from django.contrib import admin

from .models import (
    CourierProviderProfile,
    PropertyProviderProfile,
    RentalProviderProfile,
    RestaurantProviderProfile,
    RideProviderProfile,
)


class BaseProviderProfileAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'user_email',
        'onboarding_status',
        'is_active',
        'created_at',
    )
    list_filter = ('onboarding_status', 'is_active', 'created_at')
    search_fields = ('business_name', 'display_name', 'user__email', 'user__full_name', 'contact_phone')
    readonly_fields = ('created_at', 'updated_at', 'submitted_at', 'reviewed_at', 'reviewed_by')
    ordering = ('-created_at',)

    fieldsets = (
        ('Provider', {
            'fields': ('user', 'business_name', 'display_name', 'is_active'),
        }),
        ('Contact & Location', {
            'fields': (
                'contact_phone', 'contact_email', 'business_address', 'city', 'state',
                'postal_code', 'country', 'latitude', 'longitude',
            ),
        }),
        ('Review State', {
            'fields': (
                'onboarding_status', 'submitted_at', 'reviewed_at',
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


@admin.register(RideProviderProfile)
class RideProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Ride Onboarding', {
            'fields': (
                'legal_name', 'driver_license_number', 'driver_license_expiry',
                'vehicle_category', 'vehicle_make', 'vehicle_model', 'vehicle_year',
                'license_plate', 'vin', 'seat_capacity',
            ),
        }),
    )


@admin.register(RestaurantProviderProfile)
class RestaurantProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Restaurant Onboarding', {
            'fields': (
                'restaurant_name', 'cuisine_type', 'business_license_number', 'tax_id',
                'opening_time', 'closing_time', 'accepts_delivery',
            ),
        }),
    )


@admin.register(CourierProviderProfile)
class CourierProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Courier Onboarding', {
            'fields': (
                'legal_name', 'government_id_number', 'vehicle_type', 'vehicle_plate',
                'max_package_size', 'accepts_fragile_items',
            ),
        }),
    )


@admin.register(RentalProviderProfile)
class RentalProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Rental Onboarding', {
            'fields': (
                'company_registration_number', 'tax_id', 'fleet_size',
                'handover_address', 'offers_vehicle_delivery',
            ),
        }),
    )


@admin.register(PropertyProviderProfile)
class PropertyProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Property Onboarding', {
            'fields': (
                'host_legal_name', 'business_registration_number',
                'property_manager_license', 'emergency_contact_phone',
            ),
        }),
    )
