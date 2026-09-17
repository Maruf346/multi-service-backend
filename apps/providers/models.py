from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class ProviderServiceCategory(models.TextChoices):
    RIDES = 'rides', 'Ride'
    RESTAURANTS = 'restaurants', 'Restaurant / Food'
    COURIER = 'courier', 'Courier'
    RENTALS = 'rentals', 'Car Rental'
    PROPERTIES = 'properties', 'Property / Room'


class ProviderOnboardingStatus(models.TextChoices):
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


class AbstractProviderProfile(models.Model):
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
        related_name='reviewed_%(class)s_profiles',
    )
    review_note = models.TextField(blank=True, default='')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    service_category = None

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name or self.business_name or str(self.user_id)

    @property
    def is_approved(self):
        return self.approval_status == ProviderApprovalStatus.APPROVED

    def clean(self):
        super().clean()
        if self.user_id and provider_profile_exists_for_user(self.user_id, exclude_model=type(self)):
            raise ValidationError('A provider account can only have one provider profile type.')

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


class RideProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RIDES
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_provider_profile')
    legal_name = models.CharField(max_length=160)
    driver_license_number = models.CharField(max_length=80)
    driver_license_expiry = models.DateField(null=True, blank=True)
    vehicle_category = models.CharField(max_length=80, blank=True, default='')
    vehicle_make = models.CharField(max_length=80, blank=True, default='')
    vehicle_model = models.CharField(max_length=80, blank=True, default='')
    vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
    license_plate = models.CharField(max_length=40, blank=True, default='')
    vin = models.CharField(max_length=80, blank=True, default='')
    seat_capacity = models.PositiveSmallIntegerField(null=True, blank=True)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['approval_status', 'onboarding_status'])]


class RestaurantProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RESTAURANTS
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='restaurant_provider_profile')
    restaurant_name = models.CharField(max_length=160)
    cuisine_type = models.CharField(max_length=120, blank=True, default='')
    business_license_number = models.CharField(max_length=100, blank=True, default='')
    tax_id = models.CharField(max_length=100, blank=True, default='')
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    accepts_delivery = models.BooleanField(default=True)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['approval_status', 'onboarding_status'])]


class CourierProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.COURIER
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courier_provider_profile')
    legal_name = models.CharField(max_length=160)
    government_id_number = models.CharField(max_length=100, blank=True, default='')
    vehicle_type = models.CharField(max_length=80, blank=True, default='')
    vehicle_plate = models.CharField(max_length=40, blank=True, default='')
    max_package_size = models.CharField(max_length=80, blank=True, default='')
    accepts_fragile_items = models.BooleanField(default=False)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['approval_status', 'onboarding_status'])]


class RentalProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RENTALS
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rental_provider_profile')
    company_registration_number = models.CharField(max_length=100, blank=True, default='')
    tax_id = models.CharField(max_length=100, blank=True, default='')
    fleet_size = models.PositiveIntegerField(default=0)
    handover_address = models.CharField(max_length=255, blank=True, default='')
    offers_vehicle_delivery = models.BooleanField(default=False)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['approval_status', 'onboarding_status'])]


class PropertyProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.PROPERTIES
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_provider_profile')
    host_legal_name = models.CharField(max_length=160)
    business_registration_number = models.CharField(max_length=100, blank=True, default='')
    property_manager_license = models.CharField(max_length=100, blank=True, default='')
    emergency_contact_phone = models.CharField(max_length=32, blank=True, default='')

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['approval_status', 'onboarding_status'])]


PROVIDER_PROFILE_MODELS = {
    ProviderServiceCategory.RIDES: RideProviderProfile,
    ProviderServiceCategory.RESTAURANTS: RestaurantProviderProfile,
    ProviderServiceCategory.COURIER: CourierProviderProfile,
    ProviderServiceCategory.RENTALS: RentalProviderProfile,
    ProviderServiceCategory.PROPERTIES: PropertyProviderProfile,
}


def provider_profile_exists_for_user(user_id, exclude_model=None):
    for model in PROVIDER_PROFILE_MODELS.values():
        if exclude_model is not None and model is exclude_model:
            continue
        if model.objects.filter(user_id=user_id).exists():
            return True
    return False


def get_provider_profile_for_user(user):
    if not user or not getattr(user, 'is_authenticated', False):
        return None
    for model in PROVIDER_PROFILE_MODELS.values():
        try:
            return model.objects.get(user=user)
        except model.DoesNotExist:
            continue
    return None
