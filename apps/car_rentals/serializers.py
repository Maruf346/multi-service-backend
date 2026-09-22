from django.db.models import Avg
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.providers.models import RentalProviderProfile
from apps.providers.serializers import RentalProviderProfileSerializer
from .models import (
    CarRentalBooking,
    CarRentalBookingStatus,
    CarRentalPaymentStatus,
    CarRentalReview,
    RentalFuelType,
    RentalTransmission,
    RentalVehicle,
    RentalVehicleCategory,
    RentalVehicleMedia,
)
from .services import CarRentalService


class CarRentalDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RentalProviderPublicSerializer(RentalProviderProfileSerializer):
    class Meta(RentalProviderProfileSerializer.Meta):
        fields = RentalProviderProfileSerializer.Meta.fields
        read_only_fields = fields


class RentalVehicleMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalVehicleMedia
        fields = ['id', 'image', 'caption', 'display_order', 'created_at']
        read_only_fields = ['id', 'created_at']


class RentalVehicleSerializer(serializers.ModelSerializer):
    provider = RentalProviderPublicSerializer(read_only=True)
    handover_zones = serializers.ListField(child=serializers.CharField(), required=False)
    media = RentalVehicleMediaSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = RentalVehicle
        fields = [
            'id', 'provider', 'name', 'make', 'model', 'year', 'category', 'license_plate',
            'rtd_livery_tag', 'engine_powertrain', 'seating_capacity', 'luggage_capacity',
            'transmission', 'fuel_type', 'fuel_tank', 'description', 'location', 'daily_rate',
            'currency', 'security_escrow_deposit', 'pre_auth_amount', 'minimum_rental_period_days',
            'available', 'handover_zones', 'media', 'average_rating', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'provider', 'media', 'average_rating', 'created_at', 'updated_at']

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_average_rating(self, obj):
        reviews = getattr(obj, 'reviews', None)
        if reviews is None:
            return None
        value = obj.reviews.aggregate_avg if hasattr(obj.reviews, 'aggregate_avg') else None
        return value

    def validate_handover_zones(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each handover zone must be a string.')
        return value


class RentalVehicleWriteSerializer(serializers.ModelSerializer):
    handover_zones = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = RentalVehicle
        fields = [
            'name', 'make', 'model', 'year', 'category', 'license_plate', 'rtd_livery_tag',
            'engine_powertrain', 'seating_capacity', 'luggage_capacity', 'transmission',
            'fuel_type', 'fuel_tank', 'description', 'location', 'daily_rate', 'currency',
            'security_escrow_deposit', 'pre_auth_amount', 'minimum_rental_period_days',
            'available', 'handover_zones',
        ]

    def validate_handover_zones(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each handover zone must be a string.')
        return value


class RentalVehicleMediaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RentalVehicleMedia
        fields = ['image', 'caption', 'display_order']


class CarRentalQuoteRequestSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField(min_value=1)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        try:
            attrs['vehicle'] = RentalVehicle.objects.select_related('provider').get(pk=attrs.pop('vehicle_id'))
        except RentalVehicle.DoesNotExist:
            raise serializers.ValidationError({'vehicle_id': 'Vehicle was not found.'})
        return attrs


class CarRentalQuoteResponseSerializer(serializers.Serializer):
    rental_days = serializers.IntegerField()
    daily_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    rental_subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    vat_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    security_escrow_deposit = serializers.DecimalField(max_digits=10, decimal_places=2)
    pre_auth_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class CarRentalReviewSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = CarRentalReview
        fields = ['id', 'rating', 'notes', 'stood_out', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class CarRentalBookingSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone_number = serializers.CharField(source='customer.phone_number', read_only=True)
    provider = RentalProviderPublicSerializer(read_only=True)
    vehicle = RentalVehicleSerializer(read_only=True)
    review = CarRentalReviewSerializer(read_only=True)

    class Meta:
        model = CarRentalBooking
        fields = [
            'id', 'booking_number', 'customer', 'customer_email', 'customer_full_name',
            'customer_phone_number', 'provider', 'vehicle', 'status', 'pickup_handover_station',
            'pickup_latitude', 'pickup_longitude', 'pickup_place_id', 'start_date', 'end_date',
            'handover_time', 'deliver_to_villa_or_hotel', 'delivery_address', 'customer_note',
            'rental_days', 'currency', 'daily_rate', 'rental_subtotal', 'vat_amount',
            'security_escrow_deposit', 'pre_auth_amount', 'total_amount',
            'payment_method_reference', 'payment_status', 'requested_at', 'confirmed_at',
            'declined_at', 'completed_at', 'cancelled_at', 'cancelled_by', 'decision_note',
            'cancellation_reason', 'review', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class CarRentalBookingCreateSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField(min_value=1)
    pickup_handover_station = serializers.CharField(max_length=255)
    pickup_latitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    pickup_longitude = serializers.DecimalField(max_digits=9, decimal_places=6, required=False)
    pickup_place_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    handover_time = serializers.TimeField()
    deliver_to_villa_or_hotel = serializers.BooleanField(default=False)
    delivery_address = serializers.CharField(required=False, allow_blank=True, max_length=255)
    customer_note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    payment_method_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        try:
            attrs['vehicle'] = RentalVehicle.objects.select_related('provider').get(pk=attrs.pop('vehicle_id'))
        except RentalVehicle.DoesNotExist:
            raise serializers.ValidationError({'vehicle_id': 'Vehicle was not found.'})
        if attrs.get('deliver_to_villa_or_hotel') and not attrs.get('delivery_address'):
            raise serializers.ValidationError({'delivery_address': 'Delivery address is required when villa/hotel delivery is selected.'})
        return attrs

    def create(self, validated_data):
        return CarRentalService.create_booking(self.context['request'].user, validated_data)


class CarRentalBookingDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CarRentalBookingCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CarRentalPaymentStatusUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=CarRentalPaymentStatus.choices)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)


class CarRentalReviewCreateSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = CarRentalReview
        fields = ['rating', 'notes', 'stood_out']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class CarRentalProviderStatsSerializer(serializers.Serializer):
    total_vehicles = serializers.IntegerField()
    available_vehicles = serializers.IntegerField()
    requested_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    total_reviews = serializers.IntegerField()


class CarRentalBookingActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    booking = CarRentalBookingSerializer()


class CarRentalReviewResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    review = CarRentalReviewSerializer()


class RentalProviderListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RentalProviderPublicSerializer(many=True)


class RentalVehicleListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RentalVehicleSerializer(many=True)


class CarRentalBookingListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CarRentalBookingSerializer(many=True)


class CarRentalReviewListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CarRentalReviewSerializer(many=True)
