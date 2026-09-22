from django.contrib import admin

from .models import CarRentalBooking, CarRentalReview, RentalVehicle, RentalVehicleMedia


class RentalVehicleMediaInline(admin.TabularInline):
    model = RentalVehicleMedia
    extra = 0


@admin.register(RentalVehicle)
class RentalVehicleAdmin(admin.ModelAdmin):
    list_display = ('id', 'provider', 'name', 'make', 'model', 'year', 'category', 'daily_rate', 'available')
    list_filter = ('category', 'available', 'transmission', 'fuel_type', 'created_at')
    search_fields = ('name', 'make', 'model', 'license_plate', 'provider__company_or_host_legal_name')
    inlines = [RentalVehicleMediaInline]


@admin.register(CarRentalBooking)
class CarRentalBookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_number', 'customer', 'provider', 'vehicle', 'status', 'total_amount', 'payment_status', 'created_at')
    list_filter = ('status', 'payment_status', 'deliver_to_villa_or_hotel', 'created_at')
    search_fields = ('booking_number', 'customer__email', 'provider__company_or_host_legal_name', 'vehicle__name', 'vehicle__license_plate')


@admin.register(CarRentalReview)
class CarRentalReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking', 'customer', 'provider', 'vehicle', 'rating', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('booking__booking_number', 'customer__email', 'provider__company_or_host_legal_name', 'vehicle__name')
