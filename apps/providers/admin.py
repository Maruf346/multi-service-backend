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
                'profile_photo', 'legal_name', 'public_service_driver_license',
                'public_service_driver_license_file', 'nid_card_file',
                'bahamian_driving_license_file', 'car_registration_file',
                'vehicle_image', 'vehicle_category', 'vehicle_make', 'vehicle_model',
                'vehicle_year', 'license_plate', 'vin', 'seat_capacity',
                'online_accepting_requests',
            ),
        }),
    )


@admin.register(RestaurantProviderProfile)
class RestaurantProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Restaurant Onboarding', {
            'fields': (
                'restaurant_photo', 'logo', 'restaurant_name', 'cuisine_concept',
                'island_service_hub', 'kitchen_dispatch_address', 'kitchen_latitude',
                'kitchen_longitude', 'manager_or_head_chef_name', 'commercial_line',
                'billing_email', 'business_license_number', 'tax_id',
                'commercial_license_file', 'average_prep_window', 'operating_hours',
                'accepting_orders',
            ),
        }),
    )


@admin.register(CourierProviderProfile)
class CourierProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Courier Onboarding', {
            'fields': (
                'profile_photo', 'legal_name', 'operating_island_zone', 'transport_mode',
                'driver_license_number', 'driver_license_file', 'courier_permit_file',
                'police_record_certificate_file', 'online_accepting_dispatch',
            ),
        }),
    )


@admin.register(RentalProviderProfile)
class RentalProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Rental Onboarding', {
            'fields': (
                'logo', 'company_or_host_legal_name', 'operational_contact_name',
                'business_contact_number', 'primary_operating_base', 'rental_license_number',
                'business_license_permit_file', 'rental_license_file',
                'estimated_active_fleet_size',
            ),
        }),
    )


@admin.register(PropertyProviderProfile)
class PropertyProviderProfileAdmin(BaseProviderProfileAdmin):
    fieldsets = BaseProviderProfileAdmin.fieldsets + (
        ('Property Onboarding', {
            'fields': (
                'logo', 'host_name', 'official_host_email', 'mobile_phone',
                'primary_property_location', 'property_typology', 'estimated_portfolio_scale',
                'tourism_license_number', 'tourism_license_file',
                'taxpayer_identification_number', 'government_id_or_passport_file',
            ),
        }),
    )
