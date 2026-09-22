from django.contrib import admin

from .models import PropertyAvailability, PropertyListing, PropertyListingPhoto, RoomBooking, RoomReview


class PropertyListingPhotoInline(admin.TabularInline):
    model = PropertyListingPhoto
    extra = 0


@admin.register(PropertyListing)
class PropertyListingAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'title', 'island_region', 'max_guests', 'nightly_base_rate', 'is_active')
    list_filter = ('is_active', 'island_region', 'created_at')
    search_fields = ('title', 'description', 'street_address', 'provider__host_name')
    inlines = [PropertyListingPhotoInline]


@admin.register(PropertyAvailability)
class PropertyAvailabilityAdmin(admin.ModelAdmin):
    list_display = ('id', 'listing', 'date', 'is_available', 'nightly_rate_override')
    list_filter = ('is_available', 'date')
    search_fields = ('listing__title',)


@admin.register(RoomBooking)
class RoomBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_number', 'customer', 'provider', 'listing', 'status', 'total_amount', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'created_at')
    search_fields = ('booking_number', 'customer__email', 'provider__host_name', 'listing__title', 'primary_guest_full_legal_name')


@admin.register(RoomReview)
class RoomReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'customer', 'provider', 'listing', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('booking__booking_number', 'customer__email', 'provider__host_name', 'listing__title')
