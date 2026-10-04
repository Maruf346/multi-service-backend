from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import UserRole

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'full_name', 'phone_number', 'role', 'is_active',
            'profile_image', 'street_address', 'city', 'state', 'postal_code',
            'country', 'latitude', 'longitude', 'created_at', 'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profile_image(self, obj):
        if not obj.profile_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.profile_image.url)
        return obj.profile_image.url


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'full_name', 'phone_number', 'profile_image', 'street_address',
            'city', 'state', 'postal_code', 'country', 'latitude', 'longitude',
        ]
        extra_kwargs = {field: {'required': False} for field in fields}


class InitiateRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True, style={'input_type': 'password'})
    confirm_password = serializers.CharField(min_length=8, write_only=True, style={'input_type': 'password'})
    phone_number = serializers.CharField(required=False, allow_blank=True)

    def validate_email(self, value):
        value = value.lower().strip()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('This email is already registered.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError({'confirm_password': 'Passwords do not match.'})
        return attrs


class VerifyRegistrationOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain only numbers.')
        return value


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        email = attrs['email'].lower().strip()
        password = attrs['password']

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({'detail': 'Invalid email or password.'})

        if not user.check_password(password):
            raise serializers.ValidationError({'detail': 'Invalid email or password.'})
        if not user.is_active:
            raise serializers.ValidationError({'detail': 'User account is disabled.'})

        attrs['user'] = user
        return attrs


class SuperAdminLoginSerializer(LoginSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        user = attrs['user']
        if not user.is_super_admin and not user.is_staff:
            raise serializers.ValidationError({'detail': 'You do not have permission to access the dashboard.'})
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(write_only=True)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    confirm_new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'New password and confirmation do not match.'})
        return attrs


class InitiatePasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        return value.lower().strip()


class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(min_length=6, max_length=6)

    def validate_email(self, value):
        return value.lower().strip()

    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain only numbers.')
        return value


class ResetPasswordSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=8, write_only=True, style={'input_type': 'password'})
    confirm_new_password = serializers.CharField(min_length=8, write_only=True, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({'confirm_new_password': 'Passwords do not match.'})
        return attrs


class AuthTokenResponseSerializer(serializers.Serializer):
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserPublicSerializer()


class RegistrationResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    access = serializers.CharField()
    refresh = serializers.CharField()
    user = UserPublicSerializer()

class FavoriteServiceType:
    RIDES = 'rides'
    FOOD = 'food'
    COURIER = 'courier'
    CAR_RENTALS = 'car_rentals'
    PROPERTIES = 'properties'

    CHOICES = (
        (RIDES, 'Ride provider'),
        (FOOD, 'Food item'),
        (COURIER, 'Courier provider'),
        (CAR_RENTALS, 'Car rental vehicle'),
        (PROPERTIES, 'Property listing'),
    )


class FavoriteToggleSerializer(serializers.Serializer):
    service_type = serializers.ChoiceField(
        choices=FavoriteServiceType.CHOICES,
        help_text='Target favorite bucket: rides, food, courier, car_rentals, or properties.',
    )
    object_id = serializers.IntegerField(min_value=1, help_text='ID of the target service item/provider/listing.')


class FavoriteToggleResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    service_type = serializers.ChoiceField(choices=FavoriteServiceType.CHOICES)
    object_id = serializers.IntegerField()
    is_favorited = serializers.BooleanField()


class FavoriteProviderSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    display_name = serializers.CharField(allow_blank=True)
    business_name = serializers.CharField(allow_blank=True)
    service_category = serializers.CharField()
    image = serializers.CharField(allow_null=True)
    is_active = serializers.BooleanField()


class FavoriteRideProviderItemSerializer(serializers.Serializer):
    favorite_id = serializers.IntegerField()
    favorited_at = serializers.DateTimeField()
    id = serializers.IntegerField()
    legal_name = serializers.CharField(allow_blank=True)
    display_name = serializers.CharField(allow_blank=True)
    business_name = serializers.CharField(allow_blank=True)
    service_category = serializers.CharField()
    profile_photo = serializers.CharField(allow_null=True)
    vehicle_image = serializers.CharField(allow_null=True)
    vehicle_category = serializers.CharField(allow_blank=True)
    vehicle_make = serializers.CharField(allow_blank=True)
    vehicle_model = serializers.CharField(allow_blank=True)
    vehicle_year = serializers.IntegerField(allow_null=True)
    seat_capacity = serializers.IntegerField(allow_null=True)
    online_accepting_requests = serializers.BooleanField()
    is_active = serializers.BooleanField()



class FavoriteFoodCategorySummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class FavoriteRestaurantSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    restaurant_name = serializers.CharField(allow_blank=True)
    display_name = serializers.CharField(allow_blank=True)
    service_category = serializers.CharField()
    restaurant_photo = serializers.CharField(allow_null=True)
    logo = serializers.CharField(allow_null=True)
    cuisine_concept = serializers.CharField(allow_blank=True)
    island_service_hub = serializers.CharField(allow_blank=True)
    accepting_orders = serializers.BooleanField()
    is_active = serializers.BooleanField()
class FavoriteFoodItemSerializer(serializers.Serializer):
    favorite_id = serializers.IntegerField()
    favorited_at = serializers.DateTimeField()
    id = serializers.IntegerField()
    photo = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    culinary_description = serializers.CharField()
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    estimated_prep_window = serializers.CharField()
    dietary_tags = serializers.ListField(child=serializers.CharField())
    available_today = serializers.BooleanField()
    is_active = serializers.BooleanField()
    category = FavoriteFoodCategorySummarySerializer()
    restaurant = FavoriteRestaurantSummarySerializer()


class FavoriteCourierProviderItemSerializer(serializers.Serializer):
    favorite_id = serializers.IntegerField()
    favorited_at = serializers.DateTimeField()
    id = serializers.IntegerField()
    legal_name = serializers.CharField(allow_blank=True)
    display_name = serializers.CharField(allow_blank=True)
    business_name = serializers.CharField(allow_blank=True)
    service_category = serializers.CharField()
    profile_photo = serializers.CharField(allow_null=True)
    operating_island_zone = serializers.CharField(allow_blank=True)
    transport_mode = serializers.CharField(allow_blank=True)
    online_accepting_dispatch = serializers.BooleanField()
    is_active = serializers.BooleanField()


class FavoriteRentalVehicleItemSerializer(serializers.Serializer):
    favorite_id = serializers.IntegerField()
    favorited_at = serializers.DateTimeField()
    id = serializers.IntegerField()
    cover_image = serializers.CharField(allow_null=True)
    name = serializers.CharField()
    make = serializers.CharField()
    model = serializers.CharField()
    year = serializers.IntegerField()
    category = serializers.CharField()
    seating_capacity = serializers.IntegerField()
    luggage_capacity = serializers.CharField()
    transmission = serializers.CharField()
    fuel_type = serializers.CharField(allow_blank=True)
    location = serializers.CharField(allow_blank=True)
    daily_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    security_escrow_deposit = serializers.DecimalField(max_digits=10, decimal_places=2)
    pre_auth_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    minimum_rental_period_days = serializers.IntegerField()
    available = serializers.BooleanField()
    provider = FavoriteProviderSummarySerializer()


class FavoritePropertyListingItemSerializer(serializers.Serializer):
    favorite_id = serializers.IntegerField()
    favorited_at = serializers.DateTimeField()
    id = serializers.IntegerField()
    cover_image = serializers.CharField(allow_null=True)
    title = serializers.CharField()
    description = serializers.CharField()
    bedrooms = serializers.IntegerField()
    bathrooms = serializers.DecimalField(max_digits=4, decimal_places=1)
    max_guests = serializers.IntegerField()
    island_region = serializers.CharField()
    street_address = serializers.CharField()
    gated_community = serializers.CharField(allow_blank=True)
    latitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    longitude = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True)
    nightly_base_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField()
    minimum_stay_nights = serializers.IntegerField()
    cleaning_fee = serializers.DecimalField(max_digits=10, decimal_places=2)
    security_damage_deposit = serializers.DecimalField(max_digits=10, decimal_places=2)
    amenities = serializers.ListField(child=serializers.CharField())
    is_active = serializers.BooleanField()
    provider = FavoriteProviderSummarySerializer()


class FavoriteListResponseSerializer(serializers.Serializer):
    rides = FavoriteRideProviderItemSerializer(many=True)
    food = FavoriteFoodItemSerializer(many=True)
    courier = FavoriteCourierProviderItemSerializer(many=True)
    car_rentals = FavoriteRentalVehicleItemSerializer(many=True)
    properties = FavoritePropertyListingItemSerializer(many=True)
class AdminUserSerializer(serializers.ModelSerializer):
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'full_name', 'first_name', 'last_name',
            'phone_number', 'role', 'is_active', 'is_staff', 'is_superuser',
            'profile_image', 'street_address', 'city', 'state', 'postal_code',
            'country', 'latitude', 'longitude', 'date_joined', 'last_login',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profile_image(self, obj):
        if not obj.profile_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.profile_image.url)
        return obj.profile_image.url


class AdminUserListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = AdminUserSerializer(many=True)


class AdminUserStatusUpdateSerializer(serializers.Serializer):
    is_active = serializers.BooleanField()


class SuperAdminProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'full_name', 'first_name', 'last_name', 'phone_number', 'profile_image',
            'street_address', 'city', 'state', 'postal_code', 'country', 'latitude', 'longitude',
        ]
        extra_kwargs = {field: {'required': False} for field in fields}