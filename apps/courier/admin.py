from django.contrib import admin

from .models import CourierDelivery, CourierReview


@admin.register(CourierDelivery)
class CourierDeliveryAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'requested_courier', 'courier', 'status', 'package_size', 'payment_status', 'estimated_fare', 'created_at')
    list_filter = ('status', 'package_size', 'payment_status', 'fragile_or_high_value', 'transit_insurance', 'created_at')
    search_fields = ('customer__email', 'sender_name', 'sender_phone', 'recipient_name', 'recipient_phone', 'pickup_address', 'dropoff_address')
    readonly_fields = ('pickup_handover_pin',)


@admin.register(CourierReview)
class CourierReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'delivery', 'customer', 'courier', 'rating', 'tip_amount', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('customer__email', 'courier__legal_name', 'delivery__recipient_name')
