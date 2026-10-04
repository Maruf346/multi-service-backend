from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, UserFavoriteCourierProvider, UserFavoriteFoodItem, UserFavoritePropertyListing, UserFavoriteRentalVehicle, UserFavoriteRideProvider


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

@admin.register(UserFavoriteRideProvider)
class UserFavoriteRideProviderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'created_at')
    search_fields = ('user__email', 'provider__legal_name', 'provider__display_name')
    readonly_fields = ('created_at',)


@admin.register(UserFavoriteFoodItem)
class UserFavoriteFoodItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'food_item', 'created_at')
    search_fields = ('user__email', 'food_item__name', 'food_item__restaurant__restaurant_name')
    readonly_fields = ('created_at',)


@admin.register(UserFavoriteCourierProvider)
class UserFavoriteCourierProviderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'provider', 'created_at')
    search_fields = ('user__email', 'provider__legal_name', 'provider__display_name')
    readonly_fields = ('created_at',)


@admin.register(UserFavoriteRentalVehicle)
class UserFavoriteRentalVehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'vehicle', 'created_at')
    search_fields = ('user__email', 'vehicle__name', 'vehicle__make', 'vehicle__model')
    readonly_fields = ('created_at',)


@admin.register(UserFavoritePropertyListing)
class UserFavoritePropertyListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'listing', 'created_at')
    search_fields = ('user__email', 'listing__title', 'listing__provider__host_name')
    readonly_fields = ('created_at',)