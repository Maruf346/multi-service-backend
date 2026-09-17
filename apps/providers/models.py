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
    INCOMPLETE = 'incomplete', 'Incomplete'
    SUBMITTED = 'submitted', 'Submitted'
    COMPLETED = 'completed', 'Completed'


class RideVehicleCategory(models.TextChoices):
    LUXURY_SUV = 'luxury_suv', 'Luxury SUV'
    EXECUTIVE_SEDAN = 'executive_sedan', 'Executive Sedan'
    VIP_SPRINTER_VAN = 'vip_sprinter_van', 'VIP Sprinter / Van'


class CourierTransportMode(models.TextChoices):
    SPRINTER_VAN = 'sprinter_van_cargo_vault', 'Sprinter Van / Cargo Vault'
    MOTORCYCLE = 'motorcycle_express_scooter', 'Motorcycle / Express Scooter'
    STANDARD_SEDAN_SUV = 'standard_sedan_suv', 'Standard Sedan / SUV'
    BICYCLE_EBIKE = 'bicycle_ebike', 'Bicycle / E-Bike'


class PropertyTypology(models.TextChoices):
    LUXURY_VILLA = 'luxury_villa', 'Luxury Villa'
    PRIVATE_CAY = 'private_cay', 'Private Cay'
    MARINA_PENTHOUSE = 'marina_penthouse', 'Marina Penthouse'
    BEACHFRONT_ESTATE = 'beachfront_estate', 'Beachfront Estate'


class PropertyPortfolioScale(models.TextChoices):
    ONE_PROPERTY = '1_property', '1 Property'
    TWO_TO_FIVE = '2_5_properties', '2-5 Properties'
    SIX_PLUS = '6_plus_estates', '6+ Estates'


class AbstractProviderProfile(models.Model):
    business_name = models.CharField(max_length=160, blank=True, default='')
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
        default=ProviderOnboardingStatus.INCOMPLETE,
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
    required_onboarding_fields = (
        'business_name',
        'contact_phone',
        'contact_email',
        'business_address',
        'city',
        'country',
    )

    class Meta:
        abstract = True
        ordering = ['-created_at']

    def __str__(self):
        return self.display_name or self.business_name or str(self.user_id)

    @property
    def is_approved(self):
        return self.onboarding_status == ProviderOnboardingStatus.COMPLETED

    def clean(self):
        super().clean()
        if self.user_id and provider_profile_exists_for_user(self.user_id, exclude_model=type(self)):
            raise ValidationError('A provider account can only have one provider profile type.')

    def validate_ready_for_submission(self):
        missing = {}
        for field_name in self.required_onboarding_fields:
            value = getattr(self, field_name)
            if value in (None, '', [], {}):
                missing[field_name] = ['This field is required before submission.']
        if missing:
            raise ValidationError(missing)

    def mark_incomplete(self):
        self.onboarding_status = ProviderOnboardingStatus.INCOMPLETE
        self.submitted_at = None
        self.reviewed_at = None
        self.reviewed_by = None
        self.review_note = ''
        self.save(update_fields=['onboarding_status', 'submitted_at', 'reviewed_at', 'reviewed_by', 'review_note', 'updated_at'])

    def submit_for_review(self):
        self.validate_ready_for_submission()
        self.onboarding_status = ProviderOnboardingStatus.SUBMITTED
        self.submitted_at = timezone.now()
        self.reviewed_at = None
        self.reviewed_by = None
        self.review_note = ''
        self.save(update_fields=['onboarding_status', 'submitted_at', 'reviewed_at', 'reviewed_by', 'review_note', 'updated_at'])

    def approve(self, reviewer, note=''):
        self.onboarding_status = ProviderOnboardingStatus.COMPLETED
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note or ''
        self.save(update_fields=['onboarding_status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])

    def reject(self, reviewer, note=''):
        self.onboarding_status = ProviderOnboardingStatus.INCOMPLETE
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_note = note or ''
        self.save(update_fields=['onboarding_status', 'reviewed_by', 'reviewed_at', 'review_note', 'updated_at'])


class RideProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RIDES
    required_onboarding_fields = AbstractProviderProfile.required_onboarding_fields + (
        'profile_photo',
        'legal_name',
        'public_service_driver_license',
        'public_service_driver_license_file',
        'nid_card_file',
        'bahamian_driving_license_file',
        'car_registration_file',
        'vehicle_image',
        'vehicle_category',
        'vehicle_make',
        'vehicle_model',
        'vehicle_year',
        'seat_capacity',
        'vin',
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ride_provider_profile')
    profile_photo = models.ImageField(upload_to='providers/rides/photos/', blank=True, default='')
    legal_name = models.CharField(max_length=160, blank=True, default='')
    public_service_driver_license = models.CharField(max_length=100, blank=True, default='')
    public_service_driver_license_file = models.FileField(upload_to='providers/rides/documents/', blank=True, default='')
    nid_card_file = models.FileField(upload_to='providers/rides/documents/', blank=True, default='')
    bahamian_driving_license_file = models.FileField(upload_to='providers/rides/documents/', blank=True, default='')
    car_registration_file = models.FileField(upload_to='providers/rides/documents/', blank=True, default='')
    vehicle_image = models.ImageField(upload_to='providers/rides/vehicles/', blank=True, default='')
    vehicle_category = models.CharField(max_length=32, choices=RideVehicleCategory.choices, blank=True, default='')
    vehicle_make = models.CharField(max_length=80, blank=True, default='')
    vehicle_model = models.CharField(max_length=80, blank=True, default='')
    vehicle_year = models.PositiveSmallIntegerField(null=True, blank=True)
    license_plate = models.CharField(max_length=40, blank=True, default='')
    vin = models.CharField(max_length=80, blank=True, default='')
    seat_capacity = models.PositiveSmallIntegerField(null=True, blank=True)
    online_accepting_requests = models.BooleanField(default=False)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['onboarding_status'])]


class RestaurantProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RESTAURANTS
    required_onboarding_fields = AbstractProviderProfile.required_onboarding_fields + (
        'restaurant_photo',
        'logo',
        'restaurant_name',
        'cuisine_concept',
        'island_service_hub',
        'kitchen_dispatch_address',
        'manager_or_head_chef_name',
        'commercial_line',
        'billing_email',
        'business_license_number',
        'commercial_license_file',
        'average_prep_window',
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='restaurant_provider_profile')
    restaurant_photo = models.ImageField(upload_to='providers/restaurants/photos/', blank=True, default='')
    logo = models.ImageField(upload_to='providers/restaurants/logos/', blank=True, default='')
    restaurant_name = models.CharField(max_length=160, blank=True, default='')
    cuisine_concept = models.CharField(max_length=120, blank=True, default='')
    island_service_hub = models.CharField(max_length=120, blank=True, default='')
    kitchen_dispatch_address = models.CharField(max_length=255, blank=True, default='')
    kitchen_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    kitchen_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    manager_or_head_chef_name = models.CharField(max_length=160, blank=True, default='')
    commercial_line = models.CharField(max_length=32, blank=True, default='')
    billing_email = models.EmailField(blank=True, default='')
    business_license_number = models.CharField(max_length=100, blank=True, default='')
    tax_id = models.CharField(max_length=100, blank=True, default='')
    commercial_license_file = models.FileField(upload_to='providers/restaurants/documents/', blank=True, default='')
    average_prep_window = models.CharField(max_length=80, blank=True, default='')
    operating_hours = models.JSONField(blank=True, default=dict)
    accepting_orders = models.BooleanField(default=False)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['onboarding_status'])]


class CourierProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.COURIER
    required_onboarding_fields = AbstractProviderProfile.required_onboarding_fields + (
        'profile_photo',
        'legal_name',
        'operating_island_zone',
        'transport_mode',
        'driver_license_number',
        'driver_license_file',
        'courier_permit_file',
        'police_record_certificate_file',
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='courier_provider_profile')
    profile_photo = models.ImageField(upload_to='providers/courier/photos/', blank=True, default='')
    legal_name = models.CharField(max_length=160, blank=True, default='')
    operating_island_zone = models.CharField(max_length=120, blank=True, default='')
    transport_mode = models.CharField(max_length=40, choices=CourierTransportMode.choices, blank=True, default='')
    driver_license_number = models.CharField(max_length=100, blank=True, default='')
    driver_license_file = models.FileField(upload_to='providers/courier/documents/', blank=True, default='')
    courier_permit_file = models.FileField(upload_to='providers/courier/documents/', blank=True, default='')
    police_record_certificate_file = models.FileField(upload_to='providers/courier/documents/', blank=True, default='')
    online_accepting_dispatch = models.BooleanField(default=False)

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['onboarding_status'])]


class RentalProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.RENTALS
    required_onboarding_fields = AbstractProviderProfile.required_onboarding_fields + (
        'logo',
        'company_or_host_legal_name',
        'operational_contact_name',
        'business_contact_number',
        'primary_operating_base',
        'rental_license_number',
        'business_license_permit_file',
        'rental_license_file',
        'estimated_active_fleet_size',
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rental_provider_profile')
    logo = models.ImageField(upload_to='providers/rentals/logos/', blank=True, default='')
    company_or_host_legal_name = models.CharField(max_length=160, blank=True, default='')
    operational_contact_name = models.CharField(max_length=160, blank=True, default='')
    business_contact_number = models.CharField(max_length=32, blank=True, default='')
    primary_operating_base = models.CharField(max_length=255, blank=True, default='')
    rental_license_number = models.CharField(max_length=100, blank=True, default='')
    business_license_permit_file = models.FileField(upload_to='providers/rentals/documents/', blank=True, default='')
    rental_license_file = models.FileField(upload_to='providers/rentals/documents/', blank=True, default='')
    estimated_active_fleet_size = models.CharField(max_length=80, blank=True, default='')

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['onboarding_status'])]


class PropertyProviderProfile(AbstractProviderProfile):
    service_category = ProviderServiceCategory.PROPERTIES
    required_onboarding_fields = AbstractProviderProfile.required_onboarding_fields + (
        'logo',
        'host_name',
        'official_host_email',
        'mobile_phone',
        'primary_property_location',
        'property_typology',
        'estimated_portfolio_scale',
        'tourism_license_number',
        'taxpayer_identification_number',
        'government_id_or_passport_file',
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='property_provider_profile')
    logo = models.ImageField(upload_to='providers/properties/logos/', blank=True, default='')
    host_name = models.CharField(max_length=160, blank=True, default='')
    official_host_email = models.EmailField(blank=True, default='')
    mobile_phone = models.CharField(max_length=32, blank=True, default='')
    primary_property_location = models.CharField(max_length=255, blank=True, default='')
    property_typology = models.CharField(max_length=40, choices=PropertyTypology.choices, blank=True, default='')
    estimated_portfolio_scale = models.CharField(max_length=32, choices=PropertyPortfolioScale.choices, blank=True, default='')
    tourism_license_number = models.CharField(max_length=100, blank=True, default='')
    tourism_license_file = models.FileField(upload_to='providers/properties/documents/', blank=True, default='')
    taxpayer_identification_number = models.CharField(max_length=100, blank=True, default='')
    government_id_or_passport_file = models.FileField(upload_to='providers/properties/documents/', blank=True, default='')

    class Meta(AbstractProviderProfile.Meta):
        indexes = [models.Index(fields=['onboarding_status'])]


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
