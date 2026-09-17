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
    'onboarding_status', 'approval_status', 'submitted_at', 'reviewed_at',
    'reviewed_by', 'reviewed_by_email', 'review_note', 'is_active',
    'created_at', 'updated_at',
]

COMMON_FIELDS = [
    'id', 'user', 'user_email', 'user_full_name', 'service_category',
    'business_name', 'display_name', 'contact_phone', 'contact_email',
    'business_address', 'city', 'state', 'postal_code', 'country',
    'latitude', 'longitude', 'onboarding_status', 'approval_status',
    'submitted_at', 'reviewed_at', 'reviewed_by', 'reviewed_by_email',
    'review_note', 'is_active', 'created_at', 'updated_at',
]

COMMON_WRITE_FIELDS = [
    'business_name', 'display_name', 'contact_phone', 'contact_email',
    'business_address', 'city', 'state', 'postal_code', 'country',
    'latitude', 'longitude',
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
        fields = COMMON_FIELDS + [
            'legal_name', 'driver_license_number', 'driver_license_expiry',
            'vehicle_category', 'vehicle_make', 'vehicle_model', 'vehicle_year',
            'license_plate', 'vin', 'seat_capacity',
        ]
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RideProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideProviderProfile
        fields = COMMON_WRITE_FIELDS + [
            'legal_name', 'driver_license_number', 'driver_license_expiry',
            'vehicle_category', 'vehicle_make', 'vehicle_model', 'vehicle_year',
            'license_plate', 'vin', 'seat_capacity',
        ]


class RideProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RideProviderProfileSerializer()


class RestaurantProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = RestaurantProviderProfile
        fields = COMMON_FIELDS + [
            'restaurant_name', 'cuisine_type', 'business_license_number', 'tax_id',
            'opening_time', 'closing_time', 'accepts_delivery',
        ]
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RestaurantProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RestaurantProviderProfile
        fields = COMMON_WRITE_FIELDS + [
            'restaurant_name', 'cuisine_type', 'business_license_number', 'tax_id',
            'opening_time', 'closing_time', 'accepts_delivery',
        ]


class RestaurantProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RestaurantProviderProfileSerializer()


class CourierProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = CourierProviderProfile
        fields = COMMON_FIELDS + [
            'legal_name', 'government_id_number', 'vehicle_type', 'vehicle_plate',
            'max_package_size', 'accepts_fragile_items',
        ]
        read_only_fields = COMMON_READ_ONLY_FIELDS


class CourierProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = CourierProviderProfile
        fields = COMMON_WRITE_FIELDS + [
            'legal_name', 'government_id_number', 'vehicle_type', 'vehicle_plate',
            'max_package_size', 'accepts_fragile_items',
        ]


class CourierProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = CourierProviderProfileSerializer()


class RentalProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = RentalProviderProfile
        fields = COMMON_FIELDS + [
            'company_registration_number', 'tax_id', 'fleet_size',
            'handover_address', 'offers_vehicle_delivery',
        ]
        read_only_fields = COMMON_READ_ONLY_FIELDS


class RentalProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalProviderProfile
        fields = COMMON_WRITE_FIELDS + [
            'company_registration_number', 'tax_id', 'fleet_size',
            'handover_address', 'offers_vehicle_delivery',
        ]


class RentalProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = RentalProviderProfileSerializer()


class PropertyProviderProfileSerializer(ProviderProfileSerializerMixin):
    class Meta:
        model = PropertyProviderProfile
        fields = COMMON_FIELDS + [
            'host_legal_name', 'business_registration_number',
            'property_manager_license', 'emergency_contact_phone',
        ]
        read_only_fields = COMMON_READ_ONLY_FIELDS


class PropertyProviderProfileWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyProviderProfile
        fields = COMMON_WRITE_FIELDS + [
            'host_legal_name', 'business_registration_number',
            'property_manager_license', 'emergency_contact_phone',
        ]


class PropertyProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = PropertyProviderProfileSerializer()


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
