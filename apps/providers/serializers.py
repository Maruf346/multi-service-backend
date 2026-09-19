from rest_framework import serializers

from .models import (
    CourierProviderProfile,
    PropertyProviderProfile,
    ProviderServiceCategory,
    RentalProviderProfile,
    RestaurantProviderProfile,
    RideProviderProfile,
)


COMMON_READ_ONLY_FIELDS = [
    'id', 'user', 'user_email', 'user_full_name', 'service_category',
    'onboarding_status', 'submitted_at', 'reviewed_at',
    'reviewed_by', 'reviewed_by_email', 'review_note', 'is_active',
    'created_at', 'updated_at',
]

COMMON_FIELDS = [
    'id', 'user', 'user_email', 'user_full_name', 'service_category',
    'business_name', 'display_name', 'contact_phone', 'contact_email',
    'business_address', 'city', 'state', 'postal_code', 'country',
    'latitude', 'longitude', 'onboarding_status',
    'submitted_at', 'reviewed_at', 'reviewed_by', 'reviewed_by_email',
    'review_note', 'is_active', 'created_at', 'updated_at',
]

COMMON_WRITE_FIELDS = [
    'business_name', 'display_name', 'contact_phone', 'contact_email',
    'business_address', 'city', 'state', 'postal_code', 'country',
    'latitude', 'longitude',
]

RIDE_FIELDS = [
    'profile_photo', 'legal_name', 'public_service_driver_license',
    'public_service_driver_license_file', 'nid_card_file',
    'bahamian_driving_license_file', 'car_registration_file',
    'vehicle_image', 'vehicle_category', 'vehicle_make', 'vehicle_model',
    'vehicle_year', 'license_plate', 'vin', 'seat_capacity',
    'online_accepting_requests',
]

RESTAURANT_FIELDS = [
    'restaurant_photo', 'logo', 'restaurant_name', 'cuisine_concept',
    'island_service_hub', 'kitchen_dispatch_address', 'kitchen_latitude',
    'kitchen_longitude', 'manager_or_head_chef_name', 'commercial_line',
    'billing_email', 'business_license_number', 'tax_id',
    'commercial_license_file', 'average_prep_window', 'operating_hours',
    'accepting_orders',
]

COURIER_FIELDS = [
    'profile_photo', 'legal_name', 'operating_island_zone', 'transport_mode',
    'driver_license_number', 'driver_license_file', 'courier_permit_file',
    'police_record_certificate_file', 'online_accepting_dispatch',
]

RENTAL_FIELDS = [
    'logo', 'company_or_host_legal_name', 'operational_contact_name',
    'business_contact_number', 'primary_operating_base', 'rental_license_number',
    'business_license_permit_file', 'rental_license_file',
    'estimated_active_fleet_size',
]

PROPERTY_FIELDS = [
    'logo', 'host_name', 'official_host_email', 'mobile_phone',
    'primary_property_location', 'property_typology', 'estimated_portfolio_scale',
    'tourism_license_number', 'tourism_license_file',
    'taxpayer_identification_number', 'government_id_or_passport_file',
]


class DetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class ProviderProfileSerializerMixin(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True)
    service_category = serializers.ChoiceField(choices=ProviderServiceCategory.choices, read_only=True)


class RideProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = RideProviderProfile
        fields = COMMON_FIELDS + RIDE_FIELDS
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RideProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideProviderProfile
        fields = COMMON_WRITE_FIELDS + RIDE_FIELDS


class RideProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RideProviderProfileSerializer()


class RestaurantProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = RestaurantProviderProfile
        fields = COMMON_FIELDS + RESTAURANT_FIELDS
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RestaurantProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantProviderProfile
        fields = COMMON_WRITE_FIELDS + RESTAURANT_FIELDS


class RestaurantProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RestaurantProviderProfileSerializer()


class CourierProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = CourierProviderProfile
        fields = COMMON_FIELDS + COURIER_FIELDS
        read_only_fields = COMMON_READ_ONLY_FIELDS


class CourierProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierProviderProfile
        fields = COMMON_WRITE_FIELDS + COURIER_FIELDS


class CourierProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = CourierProviderProfileSerializer()


class RentalProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = RentalProviderProfile
        fields = COMMON_FIELDS + RENTAL_FIELDS
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RentalProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalProviderProfile
        fields = COMMON_WRITE_FIELDS + RENTAL_FIELDS


class RentalProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RentalProviderProfileSerializer()


class PropertyProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = PropertyProviderProfile
        fields = COMMON_FIELDS + PROPERTY_FIELDS
        read_only_fields = COMMON_READ_ONLY_FIELDS


class PropertyProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyProviderProfile
        fields = COMMON_WRITE_FIELDS + PROPERTY_FIELDS


class PropertyProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = PropertyProviderProfileSerializer()


class RideProviderProfileListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RideProviderProfileSerializer(many=True)


class RestaurantProviderProfileListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RestaurantProviderProfileSerializer(many=True)


class CourierProviderProfileListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CourierProviderProfileSerializer(many=True)


class RentalProviderProfileListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RentalProviderProfileSerializer(many=True)


class PropertyProviderProfileListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PropertyProviderProfileSerializer(many=True)

class ProviderReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


PROVIDER_SERIALIZERS = {
    ProviderServiceCategory.RIDES: RideProviderProfileSerializer,
    ProviderServiceCategory.RESTAURANTS: RestaurantProviderProfileSerializer,
    ProviderServiceCategory.COURIER: CourierProviderProfileSerializer,
    ProviderServiceCategory.RENTALS: RentalProviderProfileSerializer,
    ProviderServiceCategory.PROPERTIES: PropertyProviderProfileSerializer,
}

PROVIDER_WRITE_SERIALIZERS = {
    ProviderServiceCategory.RIDES: RideProviderProfileWriteSerializer,
    ProviderServiceCategory.RESTAURANTS: RestaurantProviderProfileWriteSerializer,
    ProviderServiceCategory.COURIER: CourierProviderProfileWriteSerializer,
    ProviderServiceCategory.RENTALS: RentalProviderProfileWriteSerializer,
    ProviderServiceCategory.PROPERTIES: PropertyProviderProfileWriteSerializer,
}
