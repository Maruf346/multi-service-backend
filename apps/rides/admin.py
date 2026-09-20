from django.contrib import admin

from .models import RideRequest, RideReview


@admin.register(RideRequest)
class RideRequestAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'driver', 'status', 'estimated_fare', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'currency', 'created_at')
    search_fields = ('customer__email', 'customer__full_name', 'pickup_address', 'destination_address')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)


@admin.register(RideReview)
class RideReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'ride', 'customer', 'driver', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__email', 'driver__user__email', 'notes')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
