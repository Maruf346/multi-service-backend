from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.providers.models import CourierProviderProfile


class CourierDeliveryStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    ASSIGNED = 'assigned', 'Assigned'
    PICKUP_ARRIVED = 'pickup_arrived', 'Pickup Arrived'
    IN_TRANSIT = 'in_transit', 'In Transit'
    DELIVERED = 'delivered', 'Delivered'
    CANCELLED = 'cancelled', 'Cancelled'


class CourierPackageSize(models.TextChoices):
    DOCUMENT = 'document', 'Document (Up to 1 kg)'
    SMALL_PARCEL = 'small_parcel', 'Small Parcel (Up to 5 kg)'
    MEDIUM_BOX = 'medium_box', 'Medium Box (Up to 15 kg)'
    LARGE_CARGO = 'large_cargo', 'Large Cargo (15+ kg / Van)'


class CourierPaymentMethod(models.TextChoices):
    CARD = 'card', 'Card'
    CASH_ON_DELIVERY = 'cash_on_delivery', 'Cash on Delivery'


class CourierPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    CASH_DUE = 'cash_due', 'Cash Due'
    REFUNDED = 'refunded', 'Refunded'


class CourierCancellationActor(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    COURIER = 'courier', 'Courier'
    SYSTEM = 'system', 'System'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


class CourierDelivery(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courier_deliveries')
    requested_courier = models.ForeignKey(
        CourierProviderProfile,
        on_delete=models.PROTECT,
        related_name='requested_courier_deliveries',
    )
    courier = models.ForeignKey(
        CourierProviderProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_courier_deliveries',
    )
    status = models.CharField(max_length=32, choices=CourierDeliveryStatus.choices, default=CourierDeliveryStatus.REQUESTED)

    pickup_address = models.CharField(max_length=255)
    pickup_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    pickup_place_id = models.CharField(max_length=255, blank=True, default='')
    sender_name = models.CharField(max_length=160)
    sender_phone = models.CharField(max_length=32)
    pickup_instructions = models.CharField(max_length=255, blank=True, default='')

    dropoff_address = models.CharField(max_length=255)
    dropoff_latitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_longitude = models.DecimalField(max_digits=9, decimal_places=6)
    dropoff_place_id = models.CharField(max_length=255, blank=True, default='')
    recipient_name = models.CharField(max_length=160)
    recipient_phone = models.CharField(max_length=32)
    delivery_instructions = models.CharField(max_length=255, blank=True, default='')

    package_size = models.CharField(max_length=32, choices=CourierPackageSize.choices)
    package_contents_description = models.TextField()
    fragile_or_high_value = models.BooleanField(default=False)

    distance_km = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    estimated_duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    estimated_delivery_at = models.DateTimeField(null=True, blank=True)
    transit_insurance = models.BooleanField(default=False)
    transit_insurance_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))

    currency = models.CharField(max_length=3, default='BSD')
    estimated_fare = models.DecimalField(max_digits=10, decimal_places=2)
    final_fare = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    payment_method = models.CharField(max_length=32, choices=CourierPaymentMethod.choices, default=CourierPaymentMethod.CARD)
    payment_method_reference = models.CharField(max_length=255, blank=True, default='')
    payment_status = models.CharField(max_length=32, choices=CourierPaymentStatus.choices, default=CourierPaymentStatus.PENDING)

    pickup_handover_pin = models.CharField(max_length=4)
    courier_current_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    courier_current_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    courier_location_updated_at = models.DateTimeField(null=True, blank=True)

    requested_at = models.DateTimeField(auto_now_add=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    pickup_arrived_at = models.DateTimeField(null=True, blank=True)
    in_transit_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=32, choices=CourierCancellationActor.choices, blank=True, default='')
    cancellation_reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
            models.Index(fields=['requested_courier', '-created_at']),
            models.Index(fields=['courier', '-created_at']),
        ]

    def __str__(self):
        return f'Courier delivery #{self.pk} - {self.status}'

    @property
    def is_terminal(self):
        return self.status in {CourierDeliveryStatus.DELIVERED, CourierDeliveryStatus.CANCELLED}

    @property
    def can_customer_cancel(self):
        return self.status in {CourierDeliveryStatus.REQUESTED, CourierDeliveryStatus.ASSIGNED}

    @property
    def public_pickup_handover_pin(self):
        if self.status in {CourierDeliveryStatus.PICKUP_ARRIVED, CourierDeliveryStatus.IN_TRANSIT, CourierDeliveryStatus.DELIVERED}:
            return self.pickup_handover_pin
        return ''

    def mark_courier_location(self, latitude, longitude):
        self.courier_current_latitude = latitude
        self.courier_current_longitude = longitude
        self.courier_location_updated_at = timezone.now()
        self.save(update_fields=['courier_current_latitude', 'courier_current_longitude', 'courier_location_updated_at', 'updated_at'])


class CourierReview(models.Model):
    delivery = models.OneToOneField(CourierDelivery, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courier_reviews')
    courier = models.ForeignKey(CourierProviderProfile, on_delete=models.CASCADE, related_name='courier_reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    stood_out = models.JSONField(blank=True, default=list)
    tip_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['courier', '-created_at'])]

    def __str__(self):
        return f'Courier review #{self.pk} - {self.rating}/5'
