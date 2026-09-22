from rest_framework import serializers

from apps.providers.models import CourierProviderProfile
from apps.providers.serializers import CourierProviderProfileSerializer
from .models import (
    CourierDelivery,
    CourierDeliveryStatus,
    CourierPackageSize,
    CourierPaymentMethod,
    CourierPaymentStatus,
    CourierReview,
)
from .services import CourierService


class CourierDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class CourierProviderPublicSerializer(CourierProviderProfileSerializer):
    class Meta(CourierProviderProfileSerializer.Meta):
        fields = CourierProviderProfileSerializer.Meta.fields
        read_only_fields = fields


class CourierFareEstimateRequestSerializer(serializers.Serializer):
    distance_km = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0)
    estimated_duration_minutes = serializers.IntegerField(required=False, min_value=0)
    package_size = serializers.ChoiceField(choices=CourierPackageSize.choices, default=CourierPackageSize.SMALL_PARCEL)
    transit_insurance = serializers.BooleanField(default=False)


class CourierFareEstimateResponseSerializer(serializers.Serializer):
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class CourierReviewSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = CourierReview
        fields = ['id', 'rating', 'notes', 'stood_out', 'tip_amount', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class CourierDeliverySerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone_number = serializers.CharField(source='customer.phone_number', read_only=True)
    requested_courier = CourierProviderPublicSerializer(read_only=True)
    courier = CourierProviderPublicSerializer(read_only=True)
    pickup_handover_pin = serializers.CharField(source='public_pickup_handover_pin', read_only=True)
    review = CourierReviewSerializer(read_only=True)

    class Meta:
        model = CourierDelivery
        fields = [
            'id', 'customer', 'customer_email', 'customer_full_name', 'customer_phone_number',
            'requested_courier', 'courier', 'status', 'pickup_address', 'pickup_latitude',
            'pickup_longitude', 'pickup_place_id', 'sender_name', 'sender_phone',
            'pickup_instructions', 'dropoff_address', 'dropoff_latitude', 'dropoff_longitude',
            'dropoff_place_id', 'recipient_name', 'recipient_phone', 'delivery_instructions',
            'package_size', 'package_contents_description', 'fragile_or_high_value',
            'distance_km', 'estimated_duration_minutes', 'estimated_delivery_at',
            'transit_insurance', 'transit_insurance_amount', 'currency', 'estimated_fare',
            'final_fare', 'tip_amount', 'payment_method', 'payment_method_reference',
            'payment_status', 'pickup_handover_pin', 'courier_current_latitude',
            'courier_current_longitude', 'courier_location_updated_at', 'requested_at',
            'assigned_at', 'pickup_arrived_at', 'in_transit_at', 'delivered_at',
            'cancelled_at', 'cancelled_by', 'cancellation_reason', 'review', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class CourierDeliveryCreateSerializer(serializers.Serializer):
    requested_courier_id = serializers.IntegerField(min_value=1)
    pickup_address = serializers.CharField(max_length=255)
    pickup_latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    pickup_longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    pickup_place_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    sender_name = serializers.CharField(max_length=160)
    sender_phone = serializers.CharField(max_length=32)
    pickup_instructions = serializers.CharField(required=False, allow_blank=True, max_length=255)
    dropoff_address = serializers.CharField(max_length=255)
    dropoff_latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    dropoff_place_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    recipient_name = serializers.CharField(max_length=160)
    recipient_phone = serializers.CharField(max_length=32)
    delivery_instructions = serializers.CharField(required=False, allow_blank=True, max_length=255)
    package_size = serializers.ChoiceField(choices=CourierPackageSize.choices)
    package_contents_description = serializers.CharField()
    fragile_or_high_value = serializers.BooleanField(default=False)
    distance_km = serializers.DecimalField(max_digits=8, decimal_places=2, required=False, min_value=0)
    estimated_duration_minutes = serializers.IntegerField(required=False, min_value=0)
    estimated_delivery_at = serializers.DateTimeField(required=False)
    transit_insurance = serializers.BooleanField(default=False)
    currency = serializers.CharField(required=False, max_length=3, default='BSD')
    estimated_fare = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    payment_method = serializers.ChoiceField(choices=CourierPaymentMethod.choices, default=CourierPaymentMethod.CARD)
    payment_method_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        try:
            attrs['requested_courier'] = CourierProviderProfile.objects.get(pk=attrs.pop('requested_courier_id'))
        except CourierProviderProfile.DoesNotExist:
            raise serializers.ValidationError({'requested_courier_id': 'Courier provider was not found.'})
        return attrs

    def create(self, validated_data):
        return CourierService.create_delivery(self.context['request'].user, validated_data)


class CourierDeliveryCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class CourierDeliveryStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=CourierDeliveryStatus.choices)


class CourierLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class CourierPaymentStatusUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=CourierPaymentStatus.choices)
    final_fare = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)


class CourierReviewCreateSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = CourierReview
        fields = ['rating', 'notes', 'stood_out', 'tip_amount']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value

    def validate_tip_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('Tip amount cannot be negative.')
        return value


class CourierProviderStatsSerializer(serializers.Serializer):
    deliveries_today = serializers.IntegerField()
    completed_deliveries_today = serializers.IntegerField()
    total_earnings = serializers.DecimalField(max_digits=10, decimal_places=2)
    average_rating = serializers.FloatField(allow_null=True)
    total_reviews = serializers.IntegerField()


class CourierDeliveryActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    delivery = CourierDeliverySerializer()


class CourierReviewResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    review = CourierReviewSerializer()


class CourierProviderListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CourierProviderPublicSerializer(many=True)


class CourierDeliveryListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CourierDeliverySerializer(many=True)


class CourierReviewListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = CourierReviewSerializer(many=True)
