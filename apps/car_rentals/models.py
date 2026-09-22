from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.providers.models import RentalProviderProfile


class RentalVehicleCategory(models.TextChoices):
    LUXURY_SUV = 'luxury_suv', 'Luxury SUV'
    EXECUTIVE_SEDAN = 'executive_sedan', 'Executive Sedan'
    SPORTS_CAR = 'sports_car', 'Sports Car'
    CONVERTIBLE = 'convertible', 'Convertible'
    VIP_VAN = 'vip_van', 'VIP Van / Sprinter'
    ELECTRIC_LUXURY = 'electric_luxury', 'Electric Luxury'


class RentalTransmission(models.TextChoices):
    AUTOMATIC = 'automatic', 'Automatic'
    MANUAL = 'manual', 'Manual'


class RentalFuelType(models.TextChoices):
    GASOLINE = 'gasoline', 'Gasoline'
    DIESEL = 'diesel', 'Diesel'
    HYBRID = 'hybrid', 'Hybrid'
    ELECTRIC = 'electric', 'Electric'


class CarRentalBookingStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    CONFIRMED = 'confirmed', 'Confirmed'
    DECLINED = 'declined', 'Declined'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class CarRentalPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PRE_AUTHORIZED = 'pre_authorized', 'Pre-Authorized'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class CarRentalCancellationActor(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    PROVIDER = 'provider', 'Provider'
    SYSTEM = 'system', 'System'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


class RentalVehicle(models.Model):
    provider = models.ForeignKey(RentalProviderProfile, on_delete=models.CASCADE, related_name='rental_vehicles')
    name = models.CharField(max_length=160)
    make = models.CharField(max_length=80)
    model = models.CharField(max_length=80)
    year = models.PositiveSmallIntegerField()
    category = models.CharField(max_length=40, choices=RentalVehicleCategory.choices)
    license_plate = models.CharField(max_length=40)
    rtd_livery_tag = models.CharField(max_length=80, blank=True, default='')
    engine_powertrain = models.CharField(max_length=160, blank=True, default='')
    seating_capacity = models.PositiveSmallIntegerField()
    luggage_capacity = models.CharField(max_length=80)
    transmission = models.CharField(max_length=32, choices=RentalTransmission.choices, default=RentalTransmission.AUTOMATIC)
    fuel_type = models.CharField(max_length=32, choices=RentalFuelType.choices, blank=True, default='')
    fuel_tank = models.CharField(max_length=80, blank=True, default='')
    description = models.TextField(blank=True, default='')
    location = models.CharField(max_length=255, blank=True, default='')
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BSD')
    security_escrow_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    pre_auth_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    minimum_rental_period_days = models.PositiveSmallIntegerField(default=1)
    available = models.BooleanField(default=True)
    handover_zones = models.JSONField(blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name', 'make', 'model']
        constraints = [
            models.UniqueConstraint(fields=['provider', 'license_plate'], name='unique_rental_vehicle_plate_per_provider'),
        ]
        indexes = [
            models.Index(fields=['provider', 'available']),
            models.Index(fields=['category', 'available']),
        ]

    def __str__(self):
        return f'{self.year} {self.make} {self.model}'


class RentalVehicleMedia(models.Model):
    vehicle = models.ForeignKey(RentalVehicle, on_delete=models.CASCADE, related_name='media')
    image = models.ImageField(upload_to='car_rentals/vehicles/')
    caption = models.CharField(max_length=160, blank=True, default='')
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        indexes = [models.Index(fields=['vehicle', 'display_order'])]

    def __str__(self):
        return self.caption or f'Vehicle media #{self.pk}'


class CarRentalBooking(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='car_rental_bookings')
    provider = models.ForeignKey(RentalProviderProfile, on_delete=models.PROTECT, related_name='car_rental_bookings')
    vehicle = models.ForeignKey(RentalVehicle, on_delete=models.PROTECT, related_name='bookings')
    booking_number = models.CharField(max_length=32, unique=True, blank=True, default='')
    status = models.CharField(max_length=32, choices=CarRentalBookingStatus.choices, default=CarRentalBookingStatus.REQUESTED)

    pickup_handover_station = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    pickup_place_id = models.CharField(max_length=255, blank=True, default='')
    start_date = models.DateField()
    end_date = models.DateField()
    handover_time = models.TimeField()
    deliver_to_villa_or_hotel = models.BooleanField(default=False)
    delivery_address = models.CharField(max_length=255, blank=True, default='')
    customer_note = models.CharField(max_length=255, blank=True, default='')

    rental_days = models.PositiveSmallIntegerField()
    currency = models.CharField(max_length=3, default='BSD')
    daily_rate = models.DecimalField(max_digits=10, decimal_places=2)
    rental_subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    security_escrow_deposit = models.DecimalField(max_digits=10, decimal_places=2)
    pre_auth_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method_reference = models.CharField(max_length=255, blank=True, default='')
    payment_status = models.CharField(max_length=32, choices=CarRentalPaymentStatus.choices, default=CarRentalPaymentStatus.PENDING)

    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=32, choices=CarRentalCancellationActor.choices, blank=True, default='')
    decision_note = models.CharField(max_length=255, blank=True, default='')
    cancellation_reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['vehicle', 'start_date', 'end_date']),
        ]

    def __str__(self):
        return self.booking_number or f'Car rental booking #{self.pk}'

    @property
    def is_terminal(self):
        return self.status in {CarRentalBookingStatus.COMPLETED, CarRentalBookingStatus.CANCELLED, CarRentalBookingStatus.DECLINED}

    @property
    def can_customer_cancel(self):
        return self.status in {CarRentalBookingStatus.REQUESTED, CarRentalBookingStatus.CONFIRMED}


class CarRentalReview(models.Model):
    booking = models.OneToOneField(CarRentalBooking, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='car_rental_reviews')
    provider = models.ForeignKey(RentalProviderProfile, on_delete=models.CASCADE, related_name='car_rental_reviews')
    vehicle = models.ForeignKey(RentalVehicle, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    stood_out = models.JSONField(blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['vehicle', '-created_at']),
        ]

    def __str__(self):
        return f'Car rental review #{self.pk} - {self.rating}/5'
