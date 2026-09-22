from django.db.models import Avg
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.providers.models import PropertyProviderProfile
from apps.providers.serializers import PropertyProviderProfileSerializer
from .models import PropertyAvailability, PropertyListing, PropertyListingPhoto, RoomBooking, RoomBookingStatus, RoomPaymentStatus, RoomReview
from .services import RoomService


class RoomDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class PropertyProviderPublicSerializer(PropertyProviderProfileSerializer):
    class Meta(PropertyProviderProfileSerializer.Meta):
        fields = PropertyProviderProfileSerializer.Meta.fields
        read_only_fields = fields


class PropertyListingPhotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyListingPhoto
        fields = ['id', 'image', 'caption', 'display_order', 'is_cover', 'created_at']
        read_only_fields = ['id', 'created_at']


class PropertyListingSerializer(serializers.ModelSerializer):
    provider = PropertyProviderPublicSerializer(read_only=True)
    amenities = serializers.ListField(child=serializers.CharField(), required=False)
    photos = PropertyListingPhotoSerializer(many=True, read_only=True)
    average_rating = serializers.SerializerMethodField()

    class Meta:
        model = PropertyListing
        fields = [
            'id', 'provider', 'title', 'description', 'bedrooms', 'bathrooms', 'max_guests',
            'island_region', 'street_address', 'gated_community', 'latitude', 'longitude',
            'nightly_base_rate', 'currency', 'minimum_stay_nights', 'cleaning_fee',
            'security_damage_deposit', 'amenities', 'is_active', 'photos', 'average_rating',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'provider', 'photos', 'average_rating', 'created_at', 'updated_at']

    @extend_schema_field(serializers.FloatField(allow_null=True))
    def get_average_rating(self, obj):
        return obj.reviews.aggregate(avg=Avg('rating'))['avg']

    def validate_amenities(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each amenity must be a string.')
        return value


class PropertyListingWriteSerializer(serializers.ModelSerializer):
    amenities = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = PropertyListing
        fields = [
            'title', 'description', 'bedrooms', 'bathrooms', 'max_guests', 'island_region',
            'street_address', 'gated_community', 'latitude', 'longitude', 'nightly_base_rate',
            'currency', 'minimum_stay_nights', 'cleaning_fee', 'security_damage_deposit',
            'amenities', 'is_active',
        ]

    def validate_amenities(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each amenity must be a string.')
        return value


class PropertyListingPhotoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyListingPhoto
        fields = ['image', 'caption', 'display_order', 'is_cover']


class PropertyAvailabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAvailability
        fields = ['id', 'listing', 'date', 'is_available', 'nightly_rate_override', 'note', 'created_at', 'updated_at']
        read_only_fields = ['id', 'listing', 'created_at', 'updated_at']


class PropertyAvailabilityWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyAvailability
        fields = ['date', 'is_available', 'nightly_rate_override', 'note']


class RoomQuoteRequestSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(min_value=1)
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    number_of_persons = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        try:
            attrs['listing'] = PropertyListing.objects.select_related('provider').get(pk=attrs.pop('listing_id'))
        except PropertyListing.DoesNotExist:
            raise serializers.ValidationError({'listing_id': 'Property listing was not found.'})
        return attrs


class RoomQuoteResponseSerializer(serializers.Serializer):
    nights = serializers.IntegerField()
    nightly_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    stay_subtotal = serializers.DecimalField(max_digits=10, decimal_places=2)
    cleaning_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    security_damage_deposit = serializers.DecimalField(max_digits=10, decimal_places=2)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()


class RoomReviewSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = RoomReview
        fields = ['id', 'rating', 'notes', 'stood_out', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class RoomBookingSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone_number = serializers.CharField(source='customer.phone_number', read_only=True)
    provider = PropertyProviderPublicSerializer(read_only=True)
    listing = PropertyListingSerializer(read_only=True)
    review = RoomReviewSerializer(read_only=True)

    class Meta:
        model = RoomBooking
        fields = [
            'id', 'booking_number', 'customer', 'customer_email', 'customer_full_name',
            'customer_phone_number', 'provider', 'listing', 'status', 'check_in_date',
            'check_out_date', 'nights', 'number_of_persons', 'primary_guest_full_legal_name',
            'primary_guest_contact_number', 'primary_guest_email', 'guest_note', 'currency',
            'nightly_rate', 'stay_subtotal', 'cleaning_fee', 'security_damage_deposit',
            'total_amount', 'payment_method_reference', 'payment_status', 'requested_at',
            'confirmed_at', 'declined_at', 'completed_at', 'cancelled_at', 'cancelled_by',
            'decision_note', 'cancellation_reason', 'review', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class RoomBookingCreateSerializer(serializers.Serializer):
    listing_id = serializers.IntegerField(min_value=1)
    check_in_date = serializers.DateField()
    check_out_date = serializers.DateField()
    number_of_persons = serializers.IntegerField(min_value=1)
    primary_guest_full_legal_name = serializers.CharField(max_length=160)
    primary_guest_contact_number = serializers.CharField(max_length=32)
    primary_guest_email = serializers.EmailField()
    guest_note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    payment_method_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)

    def validate(self, attrs):
        try:
            attrs['listing'] = PropertyListing.objects.select_related('provider').get(pk=attrs.pop('listing_id'))
        except PropertyListing.DoesNotExist:
            raise serializers.ValidationError({'listing_id': 'Property listing was not found.'})
        return attrs

    def create(self, validated_data):
        return RoomService.create_booking(self.context['request'].user, validated_data)


class RoomBookingDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RoomBookingCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class RoomPaymentStatusUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=RoomPaymentStatus.choices)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)


class RoomReviewCreateSerializer(serializers.ModelSerializer):
    stood_out = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = RoomReview
        fields = ['rating', 'notes', 'stood_out']

    def validate_stood_out(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each stood_out item must be a string.')
        return value


class RoomProviderStatsSerializer(serializers.Serializer):
    total_listings = serializers.IntegerField()
    active_listings = serializers.IntegerField()
    requested_bookings = serializers.IntegerField()
    confirmed_bookings = serializers.IntegerField()
    completed_bookings = serializers.IntegerField()
    average_rating = serializers.FloatField(allow_null=True)
    total_reviews = serializers.IntegerField()


class RoomBookingActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    booking = RoomBookingSerializer()


class RoomReviewResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    review = RoomReviewSerializer()


class PropertyProviderListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PropertyProviderPublicSerializer(many=True)


class PropertyListingListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = PropertyListingSerializer(many=True)


class RoomBookingListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RoomBookingSerializer(many=True)


class RoomReviewListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RoomReviewSerializer(many=True)
