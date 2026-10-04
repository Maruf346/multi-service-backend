import logging
from django.shortcuts import get_object_or_404

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    AuthTokenResponseSerializer,
    ChangePasswordSerializer,
    InitiatePasswordResetSerializer,
    InitiateRegistrationSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegistrationResponseSerializer,
    ResetPasswordSerializer,
    SuperAdminLoginSerializer,
    UpdateProfileSerializer,
    UserPublicSerializer,
    VerifyPasswordResetOTPSerializer,
    VerifyRegistrationOTPSerializer,
)
from .services import PasswordResetService, RegistrationService

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Auth - Shared'],
    summary='Refresh JWT token',
    responses={200: AuthTokenResponseSerializer},
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=['Auth - Customer/Provider'],
    summary='Login',
    request=LoginSerializer,
    responses={200: AuthTokenResponseSerializer},
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth - SuperAdmin'],
    summary='Admin dashboard login',
    request=SuperAdminLoginSerializer,
    responses={200: AuthTokenResponseSerializer},
)
class AdminDashboardLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SuperAdminLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth - Shared'],
    summary='Logout',
    request=LogoutSerializer,
    responses={
        204: OpenApiResponse(description='Successfully logged out'),
        400: OpenApiResponse(description='Invalid or already-blacklisted token'),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError as exc:
            raise InvalidToken({'detail': str(exc)})

        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=['Auth - Customer/Provider'],
    summary='Initiate user registration',
    request=InitiateRegistrationSerializer,
    responses={200: inline_serializer(
        name='InitiateRegistrationResponse',
        fields={
            'message': serializers.CharField(),
            'email': serializers.EmailField(),
            'expires_in_seconds': serializers.IntegerField(),
        },
    )},
)
class InitiateRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = InitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = RegistrationService.initiate_registration(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            full_name=serializer.validated_data['full_name'],
            phone_number=serializer.validated_data.get('phone_number', ''),
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth - Customer/Provider'],
    summary='Verify registration OTP',
    request=VerifyRegistrationOTPSerializer,
    responses={201: RegistrationResponseSerializer},
)
class VerifyRegistrationOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = RegistrationService.verify_and_complete_registration(
            email=serializer.validated_data['email'],
            otp=serializer.validated_data['otp'],
        )
        return Response({
            'message': 'Registration successful.',
            'access': result['access'],
            'refresh': result['refresh'],
            'user': UserPublicSerializer(result['user'], context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Auth - Shared'],
    summary='Initiate password reset',
    request=InitiatePasswordResetSerializer,
    responses={200: inline_serializer(
        name='InitiatePasswordResetResponse',
        fields={
            'message': serializers.CharField(),
            'expires_in_seconds': serializers.IntegerField(),
        },
    )},
)
class InitiatePasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = InitiatePasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.initiate_password_reset(serializer.validated_data['email'])
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth - Shared'],
    summary='Verify password reset OTP',
    description='Verify the OTP sent to the user\'s email for password reset. If valid, a reset token will be returned.',
    request=VerifyPasswordResetOTPSerializer,
    responses={200: inline_serializer(
        name='VerifyPasswordResetOTPResponse',
        fields={
            'reset_token': serializers.CharField(),
            'message': serializers.CharField(),
        },
    )},
)
class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.verify_reset_otp(
            email=serializer.validated_data['email'],
            otp=serializer.validated_data['otp'],
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth - Shared'],
    summary='Reset password',
    description='Reset password using the reset token obtained after verifying the OTP.',
    request=ResetPasswordSerializer,
)
class ResetPasswordView(APIView):
    serializer_class = ResetPasswordSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.reset_password(
            reset_token=serializer.validated_data['reset_token'],
            new_password=serializer.validated_data['new_password'],
        )
        return Response({'message': result['message']}, status=status.HTTP_200_OK)


@extend_schema(tags=['Users'], summary='Get current user profile', responses={200: UserPublicSerializer})
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserPublicSerializer(request.user, context={'request': request}).data)


@extend_schema(
    tags=['Users'],
    summary='Update current user profile',
    request=UpdateProfileSerializer,
    responses={200: UserPublicSerializer},
)
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPublicSerializer(request.user, context={'request': request}).data)


@extend_schema(
    tags=['Users - Shared'],
    summary='Change password',
    description='Allows an authenticated user to change their password by providing the current password and a new password.',
    request=ChangePasswordSerializer,
    responses={200: OpenApiResponse(description='Password changed successfully')},
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'current_password': ['Incorrect current password.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        user.save(update_fields=['password', 'updated_at'])
        logger.info('Password changed for user %s', user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)

from apps.car_rentals.models import RentalVehicle
from apps.food.models import FoodItem
from apps.providers.models import (
    CourierProviderProfile,
    ProviderOnboardingStatus,
    RentalProviderProfile,
    RestaurantProviderProfile,
    RideProviderProfile,
)
from apps.room_services.models import PropertyListing
from .models import (
    UserFavoriteCourierProvider,
    UserFavoriteFoodItem,
    UserFavoritePropertyListing,
    UserFavoriteRentalVehicle,
    UserFavoriteRideProvider,
)
from .serializers import FavoriteListResponseSerializer, FavoriteServiceType, FavoriteToggleResponseSerializer, FavoriteToggleSerializer


def _file_url(request, file_field):
    if not file_field:
        return None
    try:
        url = file_field.url
    except ValueError:
        return None
    return request.build_absolute_uri(url) if request else url


def _provider_summary(request, provider, image_field_name):
    return {
        'id': provider.id,
        'display_name': provider.display_name,
        'business_name': provider.business_name,
        'service_category': provider.service_category,
        'image': _file_url(request, getattr(provider, image_field_name, None)),
        'is_active': provider.is_active,
    }


def _ride_favorite_payload(request, favorite):
    provider = favorite.provider
    return {
        'favorite_id': favorite.id,
        'favorited_at': favorite.created_at,
        'id': provider.id,
        'legal_name': provider.legal_name,
        'display_name': provider.display_name,
        'business_name': provider.business_name,
        'service_category': provider.service_category,
        'profile_photo': _file_url(request, provider.profile_photo),
        'vehicle_image': _file_url(request, provider.vehicle_image),
        'vehicle_category': provider.vehicle_category,
        'vehicle_make': provider.vehicle_make,
        'vehicle_model': provider.vehicle_model,
        'vehicle_year': provider.vehicle_year,
        'seat_capacity': provider.seat_capacity,
        'online_accepting_requests': provider.online_accepting_requests,
        'is_active': provider.is_active,
    }


def _food_favorite_payload(request, favorite):
    item = favorite.food_item
    restaurant = item.restaurant
    return {
        'favorite_id': favorite.id,
        'favorited_at': favorite.created_at,
        'id': item.id,
        'photo': _file_url(request, item.photo),
        'name': item.name,
        'culinary_description': item.culinary_description,
        'price': item.price,
        'currency': item.currency,
        'estimated_prep_window': item.estimated_prep_window,
        'dietary_tags': item.dietary_tags,
        'available_today': item.available_today,
        'is_active': item.is_active,
        'category': {
            'id': item.category_id,
            'name': item.category.name,
        },
        'restaurant': {
            'id': restaurant.id,
            'restaurant_name': restaurant.restaurant_name,
            'display_name': restaurant.display_name,
            'service_category': restaurant.service_category,
            'restaurant_photo': _file_url(request, restaurant.restaurant_photo),
            'logo': _file_url(request, restaurant.logo),
            'cuisine_concept': restaurant.cuisine_concept,
            'island_service_hub': restaurant.island_service_hub,
            'accepting_orders': restaurant.accepting_orders,
            'is_active': restaurant.is_active,
        },
    }


def _courier_favorite_payload(request, favorite):
    provider = favorite.provider
    return {
        'favorite_id': favorite.id,
        'favorited_at': favorite.created_at,
        'id': provider.id,
        'legal_name': provider.legal_name,
        'display_name': provider.display_name,
        'business_name': provider.business_name,
        'service_category': provider.service_category,
        'profile_photo': _file_url(request, provider.profile_photo),
        'operating_island_zone': provider.operating_island_zone,
        'transport_mode': provider.transport_mode,
        'online_accepting_dispatch': provider.online_accepting_dispatch,
        'is_active': provider.is_active,
    }


def _vehicle_cover_url(request, vehicle):
    media_items = list(vehicle.media.all())
    if not media_items:
        return None
    return _file_url(request, media_items[0].image)


def _rental_favorite_payload(request, favorite):
    vehicle = favorite.vehicle
    provider = vehicle.provider
    return {
        'favorite_id': favorite.id,
        'favorited_at': favorite.created_at,
        'id': vehicle.id,
        'cover_image': _vehicle_cover_url(request, vehicle),
        'name': vehicle.name,
        'make': vehicle.make,
        'model': vehicle.model,
        'year': vehicle.year,
        'category': vehicle.category,
        'seating_capacity': vehicle.seating_capacity,
        'luggage_capacity': vehicle.luggage_capacity,
        'transmission': vehicle.transmission,
        'fuel_type': vehicle.fuel_type,
        'location': vehicle.location,
        'daily_rate': vehicle.daily_rate,
        'currency': vehicle.currency,
        'security_escrow_deposit': vehicle.security_escrow_deposit,
        'pre_auth_amount': vehicle.pre_auth_amount,
        'minimum_rental_period_days': vehicle.minimum_rental_period_days,
        'available': vehicle.available,
        'provider': _provider_summary(request, provider, 'logo'),
    }


def _listing_cover_url(request, listing):
    photos = list(listing.photos.all())
    cover = next((photo for photo in photos if photo.is_cover), None) or (photos[0] if photos else None)
    return _file_url(request, cover.image) if cover else None


def _property_favorite_payload(request, favorite):
    listing = favorite.listing
    provider = listing.provider
    return {
        'favorite_id': favorite.id,
        'favorited_at': favorite.created_at,
        'id': listing.id,
        'cover_image': _listing_cover_url(request, listing),
        'title': listing.title,
        'description': listing.description,
        'bedrooms': listing.bedrooms,
        'bathrooms': listing.bathrooms,
        'max_guests': listing.max_guests,
        'island_region': listing.island_region,
        'street_address': listing.street_address,
        'gated_community': listing.gated_community,
        'latitude': listing.latitude,
        'longitude': listing.longitude,
        'nightly_base_rate': listing.nightly_base_rate,
        'currency': listing.currency,
        'minimum_stay_nights': listing.minimum_stay_nights,
        'cleaning_fee': listing.cleaning_fee,
        'security_damage_deposit': listing.security_damage_deposit,
        'amenities': listing.amenities,
        'is_active': listing.is_active,
        'provider': _provider_summary(request, provider, 'logo'),
    }


@extend_schema(
    tags=['Users - Favorites'],
    summary='List my favorite service items',
    description='Returns five separate arrays: rides, food, courier, car_rentals, and properties.',
    responses={200: FavoriteListResponseSerializer},
)
class FavoriteListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        rides = UserFavoriteRideProvider.objects.select_related('provider').filter(user=request.user)
        food = UserFavoriteFoodItem.objects.select_related('food_item', 'food_item__category', 'food_item__restaurant').filter(user=request.user)
        courier = UserFavoriteCourierProvider.objects.select_related('provider').filter(user=request.user)
        car_rentals = UserFavoriteRentalVehicle.objects.select_related('vehicle', 'vehicle__provider').prefetch_related('vehicle__media').filter(user=request.user)
        properties = UserFavoritePropertyListing.objects.select_related('listing', 'listing__provider').prefetch_related('listing__photos').filter(user=request.user)

        return Response({
            'rides': [_ride_favorite_payload(request, favorite) for favorite in rides],
            'food': [_food_favorite_payload(request, favorite) for favorite in food],
            'courier': [_courier_favorite_payload(request, favorite) for favorite in courier],
            'car_rentals': [_rental_favorite_payload(request, favorite) for favorite in car_rentals],
            'properties': [_property_favorite_payload(request, favorite) for favorite in properties],
        })


@extend_schema(
    tags=['Users - Favorites'],
    summary='Toggle a favorite service item',
    description='Adds the favorite if it does not exist; removes it if it already exists.',
    request=FavoriteToggleSerializer,
    responses={200: FavoriteToggleResponseSerializer, 404: OpenApiResponse(description='Target item was not found')},
)
class FavoriteToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FavoriteToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        service_type = serializer.validated_data['service_type']
        object_id = serializer.validated_data['object_id']

        favorite_model, favorite_field, target = self._resolve_target(service_type, object_id)
        if target is None:
            return Response({'detail': 'Favorite target was not found.'}, status=status.HTTP_404_NOT_FOUND)

        lookup = {'user': request.user, favorite_field: target}
        favorite = favorite_model.objects.filter(**lookup).first()
        if favorite:
            favorite.delete()
            return Response({
                'detail': 'Removed from favorites.',
                'service_type': service_type,
                'object_id': object_id,
                'is_favorited': False,
            })

        favorite_model.objects.create(**lookup)
        return Response({
            'detail': 'Added to favorites.',
            'service_type': service_type,
            'object_id': object_id,
            'is_favorited': True,
        }, status=status.HTTP_200_OK)

    def _resolve_target(self, service_type, object_id):
        if service_type == FavoriteServiceType.RIDES:
            target = RideProviderProfile.objects.filter(
                pk=object_id,
                onboarding_status=ProviderOnboardingStatus.COMPLETED,
                is_active=True,
            ).first()
            return UserFavoriteRideProvider, 'provider', target

        if service_type == FavoriteServiceType.FOOD:
            target = FoodItem.objects.select_related('restaurant').filter(
                pk=object_id,
                is_active=True,
                restaurant__onboarding_status=ProviderOnboardingStatus.COMPLETED,
                restaurant__is_active=True,
            ).first()
            return UserFavoriteFoodItem, 'food_item', target

        if service_type == FavoriteServiceType.COURIER:
            target = CourierProviderProfile.objects.filter(
                pk=object_id,
                onboarding_status=ProviderOnboardingStatus.COMPLETED,
                is_active=True,
            ).first()
            return UserFavoriteCourierProvider, 'provider', target

        if service_type == FavoriteServiceType.CAR_RENTALS:
            target = RentalVehicle.objects.select_related('provider').filter(
                pk=object_id,
                provider__onboarding_status=ProviderOnboardingStatus.COMPLETED,
                provider__is_active=True,
            ).first()
            return UserFavoriteRentalVehicle, 'vehicle', target

        target = PropertyListing.objects.select_related('provider').filter(
            pk=object_id,
            is_active=True,
            provider__onboarding_status=ProviderOnboardingStatus.COMPLETED,
            provider__is_active=True,
        ).first()
        return UserFavoritePropertyListing, 'listing', target


from django.contrib.auth import get_user_model
from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter
from rest_framework.settings import api_settings
from apps.users.permissions import IsSuperAdmin
from .models import UserRole
from .serializers import AdminUserListResponseSerializer, AdminUserSerializer, AdminUserStatusUpdateSerializer, SuperAdminProfileUpdateSerializer


@extend_schema(
    tags=['Users - SuperAdmin'],
    summary='List users for admin dashboard',
    parameters=[
        OpenApiParameter('page', int, required=False),
        OpenApiParameter('page_size', int, required=False),
        OpenApiParameter('search', str, required=False, description='Search email, name, username, or phone.'),
        OpenApiParameter('role', str, enum=[choice.value for choice in UserRole], required=False),
        OpenApiParameter('is_active', bool, required=False),
    ],
    responses={200: AdminUserListResponseSerializer},
)
class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    @extend_schema(operation_id='admin_list_users')
    def get(self, request):
        UserModel = get_user_model()
        queryset = UserModel.objects.all().order_by('-created_at')

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(username__icontains=search)
                | Q(full_name__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone_number__icontains=search)
            )

        role = (request.query_params.get('role') or '').strip()
        if role:
            queryset = queryset.filter(role=role)

        is_active = request.query_params.get('is_active')
        if is_active is not None and str(is_active).strip() != '':
            queryset = queryset.filter(is_active=str(is_active).strip().lower() in ('1', 'true', 'yes'))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = AdminUserSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


@extend_schema(
    tags=['Users - SuperAdmin'],
    summary='Retrieve a user for admin dashboard',
    responses={200: AdminUserSerializer, 404: OpenApiResponse(description='User not found')},
)
class AdminUserDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(operation_id='admin_retrieve_user')
    def get(self, request, pk):
        UserModel = get_user_model()
        user = get_object_or_404(UserModel, pk=pk)
        return Response(AdminUserSerializer(user, context={'request': request}).data)


@extend_schema(
    tags=['Users - SuperAdmin'],
    summary='Update user active status',
    request=AdminUserStatusUpdateSerializer,
    responses={200: AdminUserSerializer, 404: OpenApiResponse(description='User not found')},
)
class AdminUserStatusUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(operation_id='admin_update_user_status')
    def patch(self, request, pk):
        UserModel = get_user_model()
        user = get_object_or_404(UserModel, pk=pk)
        serializer = AdminUserStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.is_active = serializer.validated_data['is_active']
        user.save(update_fields=['is_active', 'updated_at'])
        return Response(AdminUserSerializer(user, context={'request': request}).data)


@extend_schema(
    tags=['Users - SuperAdmin'],
    summary='Get my SuperAdmin profile',
    responses={200: AdminUserSerializer},
)
class SuperAdminProfileView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    @extend_schema(operation_id='admin_retrieve_my_profile')
    def get(self, request):
        return Response(AdminUserSerializer(request.user, context={'request': request}).data)

    @extend_schema(
        tags=['Users - SuperAdmin'],
        operation_id='admin_update_my_profile',
        summary='Patch my SuperAdmin profile',
        request=SuperAdminProfileUpdateSerializer,
        responses={200: AdminUserSerializer},
    )
    def patch(self, request):
        serializer = SuperAdminProfileUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AdminUserSerializer(request.user, context={'request': request}).data)