from django.conf import settings
from django.db import models
from django.utils import timezone


class ProviderServiceCategory(models.TextChoices):
    RIDES = 'rides', 'Ride'
    RESTAURANTS = 'restaurants', 'Restaurant / Food'
    COURIER = 'courier', 'Courier'
    RENTALS = 'rentals', 'Car Rental'
    PROPERTIES = 'properties', 'Property / Room'


class ProviderOnboardingStatus(models.TextChoices):
    NOT_STARTED = 'not_started', 'Not Started'
    DRAFT = 'draft', 'Draft'
    SUBMITTED = 'submitted', 'Submitted'
    UNDER_REVIEW = 'under_review', 'Under Review'
    CHANGES_REQUESTED = 'changes_requested', 'Changes Requested'
    COMPLETED = 'completed', 'Completed'


class ProviderApprovalStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    APPROVED = 'approved', 'Approved'
    REJECTED = 'rejected', 'Rejected'
    SUSPENDED = 'suspended', 'Suspended'


class ProviderProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='provider_profile',
    )
    service_category = models.CharField(max_length=32, choices=ProviderServiceCategory.choices)
    business_name = models.CharField(max_length=160)
    display_name = models.CharField(max_length=160, blank=True, default='')
    contact_phone = models.CharField(max_length=32, blank=True, default='')
    contact_email = models.EmailField(blank=True, default='')
    business_address = models.CharField(max_length=255, blank=True, default='')
    city = models.CharField(max_length=100, blank=True, default='')
    state = models.CharField(max_length=100, blank=True, default='')
    postal_code = models.CharField(max_length=20, blank=True, default='')
    country = models.CharField(max_length=100, blank=True, default='')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    onboarding_status = models.CharField(
        max_length=32,
        choices=ProviderOnboardingStatus.choices,
        default=ProviderOnboardingStatus.DRAFT,
    )
    approval_status = models.CharField(
        max_length=32,
        choices=ProviderApprovalStatus.choices,
        default=ProviderApprovalStatus.PENDING,
    )
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_provider_profiles',
    )
    review_note = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['service_category', 'approval_status']),
            models.Index(fields=['onboarding_status', 'approval_status']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        return self.display_name or self.business_name or str(self.user_id)

    @property
    def is_approved(self):
        return self.approval_status == ProviderApprovalStatus.APPROVED

    def submit_for_review(self):
        self.onboarding_status = ProviderOnboardingStatus.SUBMITTED
        self.approval_status = ProviderApprovalStatus.PENDING
        self.submitted_at = timezone.now()
        self.review_note = ''
        self.save(update_fields=['onboarding_status', 'approval_status', 'submitted_at', 'review_note', 'updated_at'])

    def approve(self, reviewer, note=''):
        self.onboarding_status = ProviderOnboardingStatus.COMPLETED
        self.approval_status = ProviderApprovalStatus.APPROVED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note or ''
        self.save(update_fields=['onboarding_status', 'approval_status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

    def reject(self, reviewer, note=''):
        self.onboarding_status = ProviderOnboardingStatus.CHANGES_REQUESTED
        self.approval_status = ProviderApprovalStatus.REJECTED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note or ''
        self.save(update_fields=['onboarding_status', 'approval_status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])
