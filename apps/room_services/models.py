from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.providers.models import PropertyProviderProfile


class RoomBookingStatus(models.TextChoices):
    REQUESTED = 'requested', 'Requested'
    CONFIRMED = 'confirmed', 'Confirmed'
    DECLINED = 'declined', 'Declined'
    COMPLETED = 'completed', 'Completed'
    CANCELLED = 'cancelled', 'Cancelled'


class RoomPaymentStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    PAID = 'paid', 'Paid'
    FAILED = 'failed', 'Failed'
    REFUNDED = 'refunded', 'Refunded'


class RoomCancellationActor(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    PROVIDER = 'provider', 'Provider'
    SYSTEM = 'system', 'System'
    SUPER_ADMIN = 'super_admin', 'Super Admin'


class PropertyListing(models.Model):
    provider = models.ForeignKey(PropertyProviderProfile, on_delete=models.CASCADE, related_name='property_listings')
    title = models.CharField(max_length=180)
    description = models.TextField()
    bedrooms = models.PositiveSmallIntegerField()
    bathrooms = models.DecimalField(max_digits=4, decimal_places=1)
    max_guests = models.PositiveSmallIntegerField()
    island_region = models.CharField(max_length=120)
    street_address = models.CharField(max_length=255)
    gated_community = models.CharField(max_length=160, blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    nightly_base_rate = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='BSD')
    minimum_stay_nights = models.PositiveSmallIntegerField(default=1)
    cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    security_damage_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    amenities = models.JSONField(blank=True, default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['provider', 'is_active']),
            models.Index(fields=['island_region', 'is_active']),
            models.Index(fields=['max_guests', 'is_active']),
        ]

    def __str__(self):
        return self.title


class PropertyListingPhoto(models.Model):
    listing = models.ForeignKey(PropertyListing, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='room_services/listings/')
    caption = models.CharField(max_length=160, blank=True, default='')
    display_order = models.PositiveSmallIntegerField(default=0)
    is_cover = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'id']
        indexes = [models.Index(fields=['listing', 'display_order'])]

    def __str__(self):
        return self.caption or f'Listing photo #{self.pk}'


class PropertyAvailability(models.Model):
    listing = models.ForeignKey(PropertyListing, on_delete=models.CASCADE, related_name='availability_days')
    date = models.DateField()
    is_available = models.BooleanField(default=True)
    nightly_rate_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['date']
        constraints = [models.UniqueConstraint(fields=['listing', 'date'], name='unique_property_availability_date')]
        indexes = [models.Index(fields=['listing', 'date', 'is_available'])]

    def __str__(self):
        return f'{self.listing_id} - {self.date}'


class RoomBooking(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='room_bookings')
    provider = models.ForeignKey(PropertyProviderProfile, on_delete=models.PROTECT, related_name='room_bookings')
    listing = models.ForeignKey(PropertyListing, on_delete=models.PROTECT, related_name='bookings')
    booking_number = models.CharField(max_length=32, unique=True, blank=True, default='')
    status = models.CharField(max_length=32, choices=RoomBookingStatus.choices, default=RoomBookingStatus.REQUESTED)

    check_in_date = models.DateField()
    check_out_date = models.DateField()
    nights = models.PositiveSmallIntegerField()
    number_of_persons = models.PositiveSmallIntegerField()
    primary_guest_full_legal_name = models.CharField(max_length=160)
    primary_guest_contact_number = models.CharField(max_length=32)
    primary_guest_email = models.EmailField()
    guest_note = models.CharField(max_length=255, blank=True, default='')

    currency = models.CharField(max_length=3, default='BSD')
    nightly_rate = models.DecimalField(max_digits=10, decimal_places=2)
    stay_subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    cleaning_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    security_damage_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method_reference = models.CharField(max_length=255, blank=True, default='')
    payment_status = models.CharField(max_length=32, choices=RoomPaymentStatus.choices, default=RoomPaymentStatus.PENDING)

    requested_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=32, choices=RoomCancellationActor.choices, blank=True, default='')
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
            models.Index(fields=['listing', 'check_in_date', 'check_out_date']),
        ]

    def __str__(self):
        return self.booking_number or f'Room booking #{self.pk}'

    @property
    def is_terminal(self):
        return self.status in {RoomBookingStatus.COMPLETED, RoomBookingStatus.CANCELLED, RoomBookingStatus.DECLINED}

    @property
    def can_customer_cancel(self):
        return self.status in {RoomBookingStatus.REQUESTED, RoomBookingStatus.CONFIRMED}


class RoomReview(models.Model):
    booking = models.OneToOneField(RoomBooking, on_delete=models.CASCADE, related_name='review')
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='room_reviews')
    provider = models.ForeignKey(PropertyProviderProfile, on_delete=models.CASCADE, related_name='room_reviews')
    listing = models.ForeignKey(PropertyListing, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    notes = models.TextField(blank=True, default='')
    stood_out = models.JSONField(blank=True, default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['provider', '-created_at']),
            models.Index(fields=['listing', '-created_at']),
        ]

    def __str__(self):
        return f'Room review #{self.pk} - {self.rating}/5'
