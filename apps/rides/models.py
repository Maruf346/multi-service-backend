from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.providers.models import RideProviderProfile


class RideStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    MATCHING = 'matching', 'Matching'
    ACCEPTED = 'accepted', 'Accepted'
    ARRIVED = 'arrived', 'Driver Arrived'
    IN_PROGRESS = 'in_progress', 'In Progress'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class RidePaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class RideCancellationActor(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    DRIVER = 'driver', 'Driver'
    SYSTEM = 'system', 'System'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


class RideRequest(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_requests')
    driver = models.ForeignKey(
        RideProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='rides',
    )
    status = models.CharField(max_length=32, choices=RideStatus.choices, default=RideStatus.MATCHING)

    pickup_address = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_place_id = models.CharField(max_length=255, blank=True, default='')
    pickup_note = models.CharField(max_length=255, blank=True, default='')

    destination_address = models.CharField(max_length=255)
    destination_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    destination_place_id = models.CharField(max_length=255, blank=True, default='')

    requested_passenger_count = models.PositiveSmallIntegerField(default=1)
    requested_vehicle_category = models.CharField(max_length=32, blank=True, default='')

    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    estimated_pickup_minutes = models.PositiveIntegerField(null=True, blank=True)
    expected_driver_arrival_at = models.DateTimeField(null=True, blank=True)

    currency = models.CharField(max_length=3, default='BSD')
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2)
    final_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method_reference = models.CharField(max_length=255, blank=True, default='')
    payment_status = models.CharField(max_length=32, choices=RidePaymentStatus.choices, default=RidePaymentStatus.PENDING)

    driver_current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    driver_current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    driver_location_updated_at = models.DateTimeField(null=True, blank=True)

    accepted_at = models.DateTimeField(null=True, blank=True)
    arrived_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=32, choices=RideCancellationActor.choices, blank=True, default='')
    cancellation_reason = models.CharField(max_length=255, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['driver', '-created_at']),
        ]

    def __str__(self):
        return f'Ride #{self.pk} - {self.customer_id} - {self.status}'

    @property
    def is_terminal(self):
        return self.status in {RideStatus.COMPLETED, RideStatus.CANCELLED}

    @property
    def can_customer_cancel(self):
        return self.status in {RideStatus.REQUESTED, RideStatus.MATCHING, RideStatus.ACCEPTED}

    def mark_driver_location(self, latitude, longitude):
        self.driver_current_latitude = latitude
        self.driver_current_longitude = longitude
        self.driver_location_updated_at = timezone.now()
        self.save(update_fields=['driver_current_latitude', 'driver_current_longitude', 'driver_location_updated_at', 'updated_at'])


class RideReview(models.Model):
    ride = models.OneToOneField(RideRequest, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_reviews')
    driver = models.ForeignKey(RideProviderProfile, on_delete=models.CASCADE, related_name='ride_reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    stood_out = models.JSONField(blank=True, default=list)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['driver', '-created_at'])]

    def __str__(self):
        return f'Ride review #{self.pk} - {self.rating}/5'
