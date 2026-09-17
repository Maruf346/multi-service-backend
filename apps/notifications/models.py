import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationType(models.TextChoices):
    ACCOUNT = 'account', 'Account'
    SYSTEM_ALERT = 'system_alert', 'System Alert'
    NEW_USER = 'new_user', 'New User'
    PROVIDER_ONBOARDING_SUBMITTED = 'provider_onboarding_submitted', 'Provider Onboarding Submitted'
    PROVIDER_ONBOARDING_APPROVED = 'provider_onboarding_approved', 'Provider Onboarding Approved'
    PROVIDER_ONBOARDING_REJECTED = 'provider_onboarding_rejected', 'Provider Onboarding Rejected'
    BOOKING_CREATED = 'booking_created', 'Booking Created'
    BOOKING_STATUS_UPDATED = 'booking_status_updated', 'Booking Status Updated'
    ORDER_CREATED = 'order_created', 'Order Created'
    ORDER_STATUS_UPDATED = 'order_status_updated', 'Order Status Updated'
    RIDE_REQUESTED = 'ride_requested', 'Ride Requested'
    RIDE_STATUS_UPDATED = 'ride_status_updated', 'Ride Status Updated'
    COURIER_REQUESTED = 'courier_requested', 'Courier Requested'
    COURIER_STATUS_UPDATED = 'courier_status_updated', 'Courier Status Updated'
    RENTAL_BOOKING_CREATED = 'rental_booking_created', 'Rental Booking Created'
    RENTAL_BOOKING_STATUS_UPDATED = 'rental_booking_status_updated', 'Rental Booking Status Updated'
    PROPERTY_BOOKING_CREATED = 'property_booking_created', 'Property Booking Created'
    PROPERTY_BOOKING_STATUS_UPDATED = 'property_booking_status_updated', 'Property Booking Status Updated'
    PAYMENT_STATUS_UPDATED = 'payment_status_updated', 'Payment Status Updated'
    REVIEW_RECEIVED = 'review_received', 'Review Received'


class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'


class NotificationAudience(models.TextChoices):
    CUSTOMER = 'customer', 'Customer'
    PROVIDER = 'provider', 'Provider'
    SUPER_ADMIN = 'super_admin', 'Super Admin'
    SYSTEM = 'system', 'System'


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
    )
    notification_type = models.CharField(max_length=64, choices=NotificationType.choices)
    audience = models.CharField(
        max_length=32,
        choices=NotificationAudience.choices,
        default=NotificationAudience.CUSTOMER,
    )
    title = models.CharField(max_length=255)
    body = models.TextField()
    data = models.JSONField(default=dict, blank=True)
    priority = models.CharField(
        max_length=20,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL,
    )
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['audience', 'created_at']),
        ]

    def __str__(self):
        identifier = getattr(self.user, 'email', '') or getattr(self.user, 'phone_number', '') or str(self.user_id)
        return f'{self.title} - {identifier}'

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at', 'updated_at'])
