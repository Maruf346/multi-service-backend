from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiParameter,
    PolymorphicProxySerializer,
    extend_schema,
    extend_schema_view,
)
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.users.permissions import IsSuperAdmin
from .models import (
    PROVIDER_PROFILE_MODELS,
    ProviderOnboardingStatus,
    ProviderServiceCategory,
)
from .serializers import (
    PROVIDER_SERIALIZERS,
    PROVIDER_WRITE_SERIALIZERS,
    CourierProviderProfileSerializer,
    CourierProviderProfileListResponseSerializer,
    CourierProviderProfileWriteSerializer,
    CourierProviderSubmitResponseSerializer,
    DetailSerializer,
    PropertyProviderProfileSerializer,
    PropertyProviderProfileListResponseSerializer,
    PropertyProviderProfileWriteSerializer,
    PropertyProviderSubmitResponseSerializer,
    ProviderReviewSerializer,
    RentalProviderProfileSerializer,
    RentalProviderProfileListResponseSerializer,
    RentalProviderProfileWriteSerializer,
    RentalProviderSubmitResponseSerializer,
    RestaurantProviderProfileSerializer,
    RestaurantProviderProfileListResponseSerializer,
    RestaurantProviderProfileWriteSerializer,
    RestaurantProviderSubmitResponseSerializer,
    RideProviderProfileSerializer,
    RideProviderProfileListResponseSerializer,
    RideProviderProfileWriteSerializer,
    RideProviderSubmitResponseSerializer,
)
from .services import ProviderProfileService

SERVICE_CATEGORY_DESCRIPTION = (
    'Provider service category. Choices: '
    '`rides` = ride sharing driver/provider, '
    '`restaurants` = restaurant or food provider, '
    '`courier` = courier delivery provider, '
    '`rentals` = car rental provider, '
    '`properties` = property or room booking provider.'
)
SERVICE_CATEGORY_PARAMETER = OpenApiParameter(
    name='service_category',
    type=str,
    location=OpenApiParameter.PATH,
    required=True,
    enum=[choice.value for choice in ProviderServiceCategory],
    description=SERVICE_CATEGORY_DESCRIPTION,
)
PROVIDER_APPLICATION_RESPONSE = PolymorphicProxySerializer(
    component_name='ProviderApplication',
    serializers={
        ProviderServiceCategory.RIDES.value: RideProviderProfileSerializer,
        ProviderServiceCategory.RESTAURANTS.value: RestaurantProviderProfileSerializer,
        ProviderServiceCategory.COURIER.value: CourierProviderProfileSerializer,
        ProviderServiceCategory.RENTALS.value: RentalProviderProfileSerializer,
        ProviderServiceCategory.PROPERTIES.value: PropertyProviderProfileSerializer,
    },
    resource_type_field_name='service_category',
)
PROVIDER_APPLICATION_LIST_RESPONSE = PolymorphicProxySerializer(
    component_name='ProviderApplicationListItem',
    serializers={
        ProviderServiceCategory.RIDES.value: RideProviderProfileSerializer,
        ProviderServiceCategory.RESTAURANTS.value: RestaurantProviderProfileSerializer,
        ProviderServiceCategory.COURIER.value: CourierProviderProfileSerializer,
        ProviderServiceCategory.RENTALS.value: RentalProviderProfileSerializer,
        ProviderServiceCategory.PROPERTIES.value: PropertyProviderProfileSerializer,
    },
    resource_type_field_name='service_category',
    many=True,
)


class ProviderTypedProfileView(APIView):
    permission_classes = [IsAuthenticated]
    service_category = None

    def get_model_class(self):
        return PROVIDER_PROFILE_MODELS[self.service_category]

    def get_read_serializer(self):
        return PROVIDER_SERIALIZERS[self.service_category]

    def get_write_serializer(self):
        return PROVIDER_WRITE_SERIALIZERS[self.service_category]

    def get_existing(self, user):
        model_class = self.get_model_class()
        try:
            return model_class.objects.get(user=user)
        except model_class.DoesNotExist:
            return None

    def get(self, request):
        profile = self.get_existing(request.user)
        if not profile:
            return Response({'detail': 'Provider profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer_class = self.get_read_serializer()
        return Response(serializer_class(profile, context={'request': request}).data)

    def patch(self, request):
        existing = self.get_existing(request.user)
        if existing and existing.onboarding_status == ProviderOnboardingStatus.COMPLETED:
            return Response({'detail': 'Completed provider profiles cannot be edited here.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer_class = self.get_write_serializer()
        serializer = serializer_class(existing, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            profile, created = ProviderProfileService.upsert_profile(
                request.user,
                self.get_model_class(),
                serializer.validated_data,
                mark_incomplete=True,
            )
        except DjangoValidationError as exc:
            return Response({'detail': getattr(exc, 'message', str(exc))}, status=status.HTTP_400_BAD_REQUEST)
        read_serializer = self.get_read_serializer()
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(read_serializer(profile, context={'request': request}).data, status=status_code)


class ProviderTypedSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    service_category = None

    def get_model_class(self):
        return PROVIDER_PROFILE_MODELS[self.service_category]

    def get_existing(self, user):
        model_class = self.get_model_class()
        try:
            return model_class.objects.get(user=user)
        except model_class.DoesNotExist:
            return None

    def post(self, request):
        existing = self.get_existing(request.user)
        serializer_class = PROVIDER_WRITE_SERIALIZERS[self.service_category]
        serializer = serializer_class(existing, data=request.data, partial=bool(existing), context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            profile, _ = ProviderProfileService.submit_profile(
                request.user,
                self.get_model_class(),
                serializer.validated_data,
            )
        except DjangoValidationError as exc:
            return Response({'detail': getattr(exc, 'message', str(exc))}, status=status.HTTP_400_BAD_REQUEST)
        response_serializer = PROVIDER_SERIALIZERS[self.service_category]
        return Response({
            'detail': 'Provider profile submitted for approval.',
            'provider': response_serializer(profile, context={'request': request}).data,
        })


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - Provider'],
        summary='Get my ride provider profile',
        responses={200: RideProviderProfileSerializer, 404: DetailSerializer},
    ),
    patch=extend_schema(
        tags=['Providers - Provider'],
        summary='Save incomplete ride provider onboarding information',
        request=RideProviderProfileWriteSerializer,
        responses={200: RideProviderProfileSerializer, 201: RideProviderProfileSerializer, 400: DetailSerializer},
    ),
)
class RideProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RIDES


@extend_schema_view(
    post=extend_schema(
        tags=['Providers - Provider'],
        summary='Save and submit my ride provider profile for SuperAdmin approval',
        request=RideProviderProfileWriteSerializer,
        responses={200: RideProviderSubmitResponseSerializer, 400: DetailSerializer},
    )
)
class RideProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RIDES


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - Provider'],
        summary='Get my restaurant provider profile',
        responses={200: RestaurantProviderProfileSerializer, 404: DetailSerializer},
    ),
    patch=extend_schema(
        tags=['Providers - Provider'],
        summary='Save incomplete restaurant provider onboarding information',
        request=RestaurantProviderProfileWriteSerializer,
        responses={200: RestaurantProviderProfileSerializer, 201: RestaurantProviderProfileSerializer, 400: DetailSerializer},
    ),
)
class RestaurantProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RESTAURANTS


@extend_schema_view(
    post=extend_schema(
        tags=['Providers - Provider'],
        summary='Save and submit my restaurant provider profile for SuperAdmin approval',
        request=RestaurantProviderProfileWriteSerializer,
        responses={200: RestaurantProviderSubmitResponseSerializer, 400: DetailSerializer},
    )
)
class RestaurantProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RESTAURANTS


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - Provider'],
        summary='Get my courier provider profile',
        responses={200: CourierProviderProfileSerializer, 404: DetailSerializer},
    ),
    patch=extend_schema(
        tags=['Providers - Provider'],
        summary='Save incomplete courier provider onboarding information',
        request=CourierProviderProfileWriteSerializer,
        responses={200: CourierProviderProfileSerializer, 201: CourierProviderProfileSerializer, 400: DetailSerializer},
    ),
)
class CourierProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.COURIER


@extend_schema_view(
    post=extend_schema(
        tags=['Providers - Provider'],
        summary='Save and submit my courier provider profile for SuperAdmin approval',
        request=CourierProviderProfileWriteSerializer,
        responses={200: CourierProviderSubmitResponseSerializer, 400: DetailSerializer},
    )
)
class CourierProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.COURIER


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - Provider'],
        summary='Get my rental provider profile',
        responses={200: RentalProviderProfileSerializer, 404: DetailSerializer},
    ),
    patch=extend_schema(
        tags=['Providers - Provider'],
        summary='Save incomplete rental provider onboarding information',
        request=RentalProviderProfileWriteSerializer,
        responses={200: RentalProviderProfileSerializer, 201: RentalProviderProfileSerializer, 400: DetailSerializer},
    ),
)
class RentalProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RENTALS


@extend_schema_view(
    post=extend_schema(
        tags=['Providers - Provider'],
        summary='Save and submit my rental provider profile for SuperAdmin approval',
        request=RentalProviderProfileWriteSerializer,
        responses={200: RentalProviderSubmitResponseSerializer, 400: DetailSerializer},
    )
)
class RentalProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RENTALS


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - Provider'],
        summary='Get my property provider profile',
        responses={200: PropertyProviderProfileSerializer, 404: DetailSerializer},
    ),
    patch=extend_schema(
        tags=['Providers - Provider'],
        summary='Save incomplete property provider onboarding information',
        request=PropertyProviderProfileWriteSerializer,
        responses={200: PropertyProviderProfileSerializer, 201: PropertyProviderProfileSerializer, 400: DetailSerializer},
    ),
)
class PropertyProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.PROPERTIES


@extend_schema_view(
    post=extend_schema(
        tags=['Providers - Provider'],
        summary='Save and submit my property provider profile for SuperAdmin approval',
        request=PropertyProviderProfileWriteSerializer,
        responses={200: PropertyProviderSubmitResponseSerializer, 400: DetailSerializer},
    )
)
class PropertyProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.PROPERTIES

class SuperAdminTypedProviderProfileListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    model_class = None
    serializer_class = None
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self, request):
        queryset = self.model_class.objects.select_related('user', 'reviewed_by').order_by('-created_at')

        onboarding_status = (request.query_params.get('onboarding_status') or '').strip()
        if onboarding_status:
            queryset = queryset.filter(onboarding_status=onboarding_status)

        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).strip().lower() in ('1', 'true', 'yes'))

        search = (request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(business_name__icontains=search)
                | Q(display_name__icontains=search)
                | Q(contact_email__icontains=search)
                | Q(contact_phone__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__full_name__icontains=search)
            )
        return queryset

    def get(self, request):
        queryset = self.get_queryset(request)
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = self.serializer_class(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class SuperAdminTypedProviderProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    model_class = None
    serializer_class = None

    def get(self, request, pk):
        profile = get_object_or_404(self.model_class.objects.select_related('user', 'reviewed_by'), pk=pk)
        return Response(self.serializer_class(profile, context={'request': request}).data)


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_list_ride_provider_profiles',
        summary='List ride provider profiles',
        parameters=[
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: RideProviderProfileListResponseSerializer},
    )
)
class SuperAdminRideProviderProfileListView(SuperAdminTypedProviderProfileListView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RIDES]
    serializer_class = RideProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_retrieve_ride_provider_profile',
        summary='Retrieve ride provider profile',
        responses={200: RideProviderProfileSerializer, 404: DetailSerializer},
    )
)
class SuperAdminRideProviderProfileDetailView(SuperAdminTypedProviderProfileDetailView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RIDES]
    serializer_class = RideProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_list_restaurant_provider_profiles',
        summary='List restaurant provider profiles',
        parameters=[
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: RestaurantProviderProfileListResponseSerializer},
    )
)
class SuperAdminRestaurantProviderProfileListView(SuperAdminTypedProviderProfileListView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RESTAURANTS]
    serializer_class = RestaurantProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_retrieve_restaurant_provider_profile',
        summary='Retrieve restaurant provider profile',
        responses={200: RestaurantProviderProfileSerializer, 404: DetailSerializer},
    )
)
class SuperAdminRestaurantProviderProfileDetailView(SuperAdminTypedProviderProfileDetailView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RESTAURANTS]
    serializer_class = RestaurantProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_list_courier_provider_profiles',
        summary='List courier provider profiles',
        parameters=[
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: CourierProviderProfileListResponseSerializer},
    )
)
class SuperAdminCourierProviderProfileListView(SuperAdminTypedProviderProfileListView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.COURIER]
    serializer_class = CourierProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_retrieve_courier_provider_profile',
        summary='Retrieve courier provider profile',
        responses={200: CourierProviderProfileSerializer, 404: DetailSerializer},
    )
)
class SuperAdminCourierProviderProfileDetailView(SuperAdminTypedProviderProfileDetailView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.COURIER]
    serializer_class = CourierProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_list_rental_provider_profiles',
        summary='List rental provider profiles',
        parameters=[
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: RentalProviderProfileListResponseSerializer},
    )
)
class SuperAdminRentalProviderProfileListView(SuperAdminTypedProviderProfileListView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RENTALS]
    serializer_class = RentalProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_retrieve_rental_provider_profile',
        summary='Retrieve rental provider profile',
        responses={200: RentalProviderProfileSerializer, 404: DetailSerializer},
    )
)
class SuperAdminRentalProviderProfileDetailView(SuperAdminTypedProviderProfileDetailView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.RENTALS]
    serializer_class = RentalProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_list_property_provider_profiles',
        summary='List property provider profiles',
        parameters=[
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
            OpenApiParameter('search', str, required=False),
        ],
        responses={200: PropertyProviderProfileListResponseSerializer},
    )
)
class SuperAdminPropertyProviderProfileListView(SuperAdminTypedProviderProfileListView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.PROPERTIES]
    serializer_class = PropertyProviderProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['Providers - SuperAdmin'],
        operation_id='admin_retrieve_property_provider_profile',
        summary='Retrieve property provider profile',
        responses={200: PropertyProviderProfileSerializer, 404: DetailSerializer},
    )
)
class SuperAdminPropertyProviderProfileDetailView(SuperAdminTypedProviderProfileDetailView):
    model_class = PROVIDER_PROFILE_MODELS[ProviderServiceCategory.PROPERTIES]
    serializer_class = PropertyProviderProfileSerializer

class SuperAdminProviderProfileListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - SuperAdmin'],
        summary='List provider onboarding applications across service types',
        description=SERVICE_CATEGORY_DESCRIPTION,
        parameters=[
            OpenApiParameter('service_category', str, enum=[choice.value for choice in ProviderServiceCategory], required=False, description=SERVICE_CATEGORY_DESCRIPTION),
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
        ],
        responses={200: PROVIDER_APPLICATION_LIST_RESPONSE},
    )
    def get(self, request):
        items = []
        categories = [request.query_params.get('service_category')] if request.query_params.get('service_category') else PROVIDER_PROFILE_MODELS.keys()
        for category in categories:
            model_class = PROVIDER_PROFILE_MODELS.get(category)
            serializer_class = PROVIDER_SERIALIZERS.get(category)
            if not model_class or not serializer_class:
                continue
            queryset = model_class.objects.select_related('user', 'reviewed_by').order_by('-created_at')
            onboarding_status = (request.query_params.get('onboarding_status') or '').strip()
            if onboarding_status:
                queryset = queryset.filter(onboarding_status=onboarding_status)
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                queryset = queryset.filter(is_active=str(is_active).strip().lower() in ('1', 'true', 'yes'))
            items.extend(serializer_class(obj, context={'request': request}).data for obj in queryset)
        items.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        return Response(items)


class SuperAdminProviderProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - SuperAdmin'],
        summary='Get provider onboarding details by service type',
        description=SERVICE_CATEGORY_DESCRIPTION,
        parameters=[SERVICE_CATEGORY_PARAMETER],
        responses={200: PROVIDER_APPLICATION_RESPONSE, 404: DetailSerializer},
    )
    def get(self, request, service_category, pk):
        profile, serializer_class = _get_profile_and_serializer(service_category, pk)
        return Response(serializer_class(profile, context={'request': request}).data)


class SuperAdminProviderApproveView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - SuperAdmin'],
        summary='Approve provider onboarding by service type',
        description=SERVICE_CATEGORY_DESCRIPTION,
        parameters=[SERVICE_CATEGORY_PARAMETER],
        request=ProviderReviewSerializer,
        responses={200: PROVIDER_APPLICATION_RESPONSE, 404: DetailSerializer},
    )
    def post(self, request, service_category, pk):
        profile, serializer_class = _get_profile_and_serializer(service_category, pk)
        serializer = ProviderReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = ProviderProfileService.approve(profile, reviewer=request.user, note=serializer.validated_data.get('note', ''))
        return Response(serializer_class(profile, context={'request': request}).data)


class SuperAdminProviderRejectView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - SuperAdmin'],
        summary='Reject provider onboarding by service type',
        description=SERVICE_CATEGORY_DESCRIPTION,
        parameters=[SERVICE_CATEGORY_PARAMETER],
        request=ProviderReviewSerializer,
        responses={200: PROVIDER_APPLICATION_RESPONSE, 404: DetailSerializer},
    )
    def post(self, request, service_category, pk):
        profile, serializer_class = _get_profile_and_serializer(service_category, pk)
        serializer = ProviderReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = ProviderProfileService.reject(profile, reviewer=request.user, note=serializer.validated_data.get('note', ''))
        return Response(serializer_class(profile, context={'request': request}).data)


def _get_profile_and_serializer(service_category, pk):
    model_class = PROVIDER_PROFILE_MODELS.get(service_category)
    serializer_class = PROVIDER_SERIALIZERS.get(service_category)
    if not model_class or not serializer_class:
        raise Http404
    return get_object_or_404(model_class.objects.select_related('user', 'reviewed_by'), pk=pk), serializer_class
