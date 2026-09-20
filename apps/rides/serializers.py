from rest_framework import serializers

from apps.providers.serializers import RideProviderProfileSerializer
from .models import RideCancellationActor, RidePaymentStatus, RideRequest, RideReview, RideStatus
from .services import RideService


class RideDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class RideFareEstimateRequestSerializer(serializers.Serializer):
    distance_km = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0)
    estimated_duration_minutes = serializers.IntegerField(required=False, min_value=0)
    requested_passenger_count = serializers.IntegerField(default=1, min_value=1, max_value=20)


class RideFareEstimateResponseSerializer(serializers.Serializer):
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class RideReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideReview
        fields = ['id', 'rating', 'notes', 'stood_out', 'tip_amount', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_stood_out(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('stood_out must be a list of selected labels.')
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class RideRequestSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone_number = serializers.CharField(source='customer.phone_number', read_only=True)
    driver = RideProviderProfileSerializer(read_only=True)
    review = RideReviewSerializer(read_only=True)

    class Meta:
        model = RideRequest
        fields = [
            'id', 'customer', 'customer_email', 'customer_full_name', 'customer_phone_number',
            'driver', 'status', 'pickup_address', 'pickup_latitude', 'pickup_longitude',
            'pickup_place_id', 'pickup_note', 'destination_address', 'destination_latitude',
            'destination_longitude', 'destination_place_id', 'requested_passenger_count',
            'requested_vehicle_category', 'distance_km', 'estimated_duration_minutes',
            'estimated_pickup_minutes', 'expected_driver_arrival_at', 'currency',
            'estimated_fare', 'final_fare', 'tip_amount', 'payment_method_reference',
            'payment_status', 'driver_current_latitude', 'driver_current_longitude',
            'driver_location_updated_at', 'accepted_at', 'arrived_at', 'started_at',
            'completed_at', 'cancelled_at', 'cancelled_by', 'cancellation_reason',
            'review', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class RideCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideRequest
        fields = [
            'pickup_address', 'pickup_latitude', 'pickup_longitude', 'pickup_place_id',
            'pickup_note', 'destination_address', 'destination_latitude',
            'destination_longitude', 'destination_place_id', 'requested_passenger_count',
            'requested_vehicle_category', 'distance_km', 'estimated_duration_minutes',
            'estimated_pickup_minutes', 'expected_driver_arrival_at', 'currency',
            'payment_method_reference',
        ]

    def validate_requested_passenger_count(self, value):
        if value < 1:
            raise serializers.ValidationError('Passenger count must be at least 1.')
        return value

    def create(self, validated_data):
        return RideService.create_ride(self.context['request'].user, validated_data)


class RideCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RideDriverLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class RidePaymentStatusUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=RidePaymentStatus.choices)
    final_fare = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)


class RideHistoryQuerySerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=RideStatus.choices, required=False)
    past = serializers.BooleanField(required=False)


class RideAcceptResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    ride = RideRequestSerializer()


class RideReviewCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = RideReview
        fields = ['rating', 'notes', 'stood_out', 'tip_amount']

    def validate_stood_out(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('stood_out must be a list of selected labels.')
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value

    def validate_tip_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('Tip amount cannot be negative.')
        return value


class RideReviewResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    review = RideReviewSerializer()


class RideStatusActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    ride = RideRequestSerializer()

class RideRequestListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RideRequestSerializer(many=True)