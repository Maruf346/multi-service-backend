from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.providers.models import CourierProviderProfile, RestaurantProviderProfile
from .models import (
    FoodItem,
    FoodItemReview,
    FoodOrder,
    FoodOrderItem,
    FoodOrderStatus,
    FoodPaymentMethod,
    FoodPaymentStatus,
    MenuCategory,
)
from .services import FoodService


class FoodDetailSerializer(serializers.Serializer):
    detail = serializers.CharField()


class OperatingHourSerializer(serializers.Serializer):
    day = serializers.CharField()
    opens_at = serializers.CharField(required=False, allow_blank=True)
    closes_at = serializers.CharField(required=False, allow_blank=True)
    is_closed = serializers.BooleanField(required=False, default=False)


class RestaurantPublicSerializer(serializers.ModelSerializer):
    service_category = serializers.CharField(read_only=True)
    operating_hours = serializers.SerializerMethodField()

    class Meta:
        model = RestaurantProviderProfile
        fields = [
            'id', 'service_category', 'restaurant_photo', 'logo', 'restaurant_name',
            'cuisine_concept', 'island_service_hub', 'kitchen_dispatch_address',
            'kitchen_latitude', 'kitchen_longitude', 'average_prep_window',
            'operating_hours', 'accepting_orders', 'is_active',
        ]
        read_only_fields = fields

    @extend_schema_field(OperatingHourSerializer(many=True))
    def get_operating_hours(self, obj):
        value = obj.operating_hours or {}
        if isinstance(value, list):
            return value
        if not isinstance(value, dict):
            return []
        hours = []
        for day, config in value.items():
            config = config if isinstance(config, dict) else {}
            hours.append({
                'day': day,
                'opens_at': config.get('opens_at', config.get('open', '')),
                'closes_at': config.get('closes_at', config.get('close', '')),
                'is_closed': bool(config.get('is_closed', False)),
            })
        return hours


class MenuCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuCategory
        fields = ['id', 'name', 'description', 'display_order', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class FoodItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    dietary_tags = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = FoodItem
        fields = [
            'id', 'category', 'category_name', 'photo', 'name', 'culinary_description',
            'price', 'currency', 'estimated_prep_window', 'dietary_tags',
            'available_today', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'category_name', 'created_at', 'updated_at']

    def validate_dietary_tags(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each dietary tag must be a string.')
        return value


class FoodItemWriteSerializer(serializers.ModelSerializer):
    dietary_tags = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = FoodItem
        fields = [
            'category', 'photo', 'name', 'culinary_description', 'price', 'currency',
            'estimated_prep_window', 'dietary_tags', 'available_today', 'is_active',
        ]

    def validate_category(self, value):
        restaurant = self.context.get('restaurant')
        if restaurant and value.restaurant_id != restaurant.id:
            raise serializers.ValidationError('Category must belong to your restaurant.')
        return value

    def validate_dietary_tags(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each dietary tag must be a string.')
        return value


class RestaurantMenuSerializer(serializers.Serializer):
    restaurant = RestaurantPublicSerializer()
    categories = MenuCategorySerializer(many=True)
    food_items = FoodItemSerializer(many=True)


class FoodOrderItemSerializer(serializers.ModelSerializer):
    review_id = serializers.IntegerField(source='review.id', read_only=True)

    class Meta:
        model = FoodOrderItem
        fields = [
            'id', 'food_item', 'item_name', 'category_name', 'quantity', 'unit_price',
            'line_total', 'currency', 'notes', 'review_id', 'created_at',
        ]
        read_only_fields = fields


class FoodItemReviewSerializer(serializers.ModelSerializer):
    impressed = serializers.ListField(child=serializers.CharField(), required=False)
    food_item_name = serializers.CharField(source='order_item.item_name', read_only=True)

    class Meta:
        model = FoodItemReview
        fields = ['id', 'order_item', 'food_item_name', 'rating', 'notes', 'impressed', 'tip_amount', 'created_at']
        read_only_fields = ['id', 'food_item_name', 'created_at']

    def validate_impressed(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each impressed item must be a string.')
        return value


class FoodOrderSerializer(serializers.ModelSerializer):
    customer_email = serializers.EmailField(source='customer.email', read_only=True)
    customer_full_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone_number = serializers.CharField(source='customer.phone_number', read_only=True)
    restaurant = RestaurantPublicSerializer(read_only=True)
    courier_user_email = serializers.EmailField(source='courier.user.email', read_only=True)
    courier_user_full_name = serializers.CharField(source='courier.user.full_name', read_only=True)
    items = FoodOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = FoodOrder
        fields = [
            'id', 'customer', 'customer_email', 'customer_full_name', 'customer_phone_number',
            'restaurant', 'courier', 'courier_user_email', 'courier_user_full_name', 'status',
            'delivery_address', 'delivery_latitude', 'delivery_longitude', 'delivery_place_id',
            'delivery_note', 'currency', 'subtotal', 'delivery_fee', 'service_fee',
            'total_amount', 'tip_amount', 'payment_method', 'payment_method_reference',
            'payment_status', 'estimated_handover_min_minutes', 'estimated_handover_max_minutes',
            'estimated_handover_at', 'courier_current_latitude', 'courier_current_longitude',
            'courier_location_updated_at', 'placed_at', 'confirmed_at', 'in_prep_at',
            'kitchen_sealed_at', 'courier_assigned_at', 'in_transit_at', 'handed_over_at',
            'cancelled_at', 'cancelled_by', 'cancellation_reason', 'items', 'created_at', 'updated_at',
        ]
        read_only_fields = fields


class FoodOrderCreateItemSerializer(serializers.Serializer):
    food_item_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1, max_value=99)
    notes = serializers.CharField(required=False, allow_blank=True, max_length=255)


class FoodOrderCreateSerializer(serializers.Serializer):
    restaurant_id = serializers.IntegerField(min_value=1)
    items = FoodOrderCreateItemSerializer(many=True)
    delivery_address = serializers.CharField(max_length=255)
    delivery_latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    delivery_longitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    delivery_place_id = serializers.CharField(required=False, allow_blank=True, max_length=255)
    delivery_note = serializers.CharField(required=False, allow_blank=True, max_length=255)
    currency = serializers.CharField(required=False, max_length=3, default='BSD')
    delivery_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    service_fee = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    tip_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)
    payment_method = serializers.ChoiceField(choices=FoodPaymentMethod.choices, default=FoodPaymentMethod.CASH_ON_DELIVERY)
    payment_method_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
    estimated_handover_min_minutes = serializers.IntegerField(required=False, min_value=0)
    estimated_handover_max_minutes = serializers.IntegerField(required=False, min_value=0)
    estimated_handover_at = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        if not attrs.get('items'):
            raise serializers.ValidationError({'items': 'At least one food item is required.'})
        try:
            attrs['restaurant'] = RestaurantProviderProfile.objects.get(pk=attrs.pop('restaurant_id'))
        except RestaurantProviderProfile.DoesNotExist:
            raise serializers.ValidationError({'restaurant_id': 'Restaurant was not found.'})
        min_minutes = attrs.get('estimated_handover_min_minutes')
        max_minutes = attrs.get('estimated_handover_max_minutes')
        if min_minutes is not None and max_minutes is not None and min_minutes > max_minutes:
            raise serializers.ValidationError({'estimated_handover_max_minutes': 'Must be greater than or equal to the minimum estimate.'})
        return attrs

    def create(self, validated_data):
        return FoodService.create_order(self.context['request'].user, validated_data)


class FoodOrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True, max_length=255)


class FoodOrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=FoodOrderStatus.choices)
    courier_profile_id = serializers.IntegerField(required=False, min_value=1)

    def validate(self, attrs):
        courier_profile_id = attrs.pop('courier_profile_id', None)
        if courier_profile_id is not None:
            try:
                attrs['courier_profile'] = CourierProviderProfile.objects.get(pk=courier_profile_id)
            except CourierProviderProfile.DoesNotExist:
                raise serializers.ValidationError({'courier_profile_id': 'Courier profile was not found.'})
        return attrs


class FoodPaymentStatusUpdateSerializer(serializers.Serializer):
    payment_status = serializers.ChoiceField(choices=FoodPaymentStatus.choices)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, min_value=0)


class FoodCourierLocationSerializer(serializers.Serializer):
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6)


class FoodItemReviewCreateSerializer(serializers.ModelSerializer):
    impressed = serializers.ListField(child=serializers.CharField(), required=False)

    class Meta:
        model = FoodItemReview
        fields = ['rating', 'notes', 'impressed', 'tip_amount']

    def validate_impressed(self, value):
        if any(not isinstance(item, str) for item in value):
            raise serializers.ValidationError('Each impressed item must be a string.')
        return value

    def validate_tip_amount(self, value):
        if value < 0:
            raise serializers.ValidationError('Tip amount cannot be negative.')
        return value


class FoodOrderActionResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    order = FoodOrderSerializer()


class FoodItemReviewResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    review = FoodItemReviewSerializer()


class RestaurantListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = RestaurantPublicSerializer(many=True)


class MenuCategoryListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = MenuCategorySerializer(many=True)


class FoodItemListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = FoodItemSerializer(many=True)


class FoodOrderListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = FoodOrderSerializer(many=True)
