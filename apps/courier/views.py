from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.providers.models import CourierProviderProfile, ProviderOnboardingStatus
from apps.users.permissions import IsCustomer, IsServiceProvider, IsSuperAdmin
from .models import CourierCancellationActor, CourierDelivery, CourierDeliveryStatus, CourierPackageSize, CourierReview
from .serializers import (
    CourierDeliveryActionResponseSerializer,
    CourierDeliveryCancelSerializer,
    CourierDeliveryCreateSerializer,
    CourierDeliveryListResponseSerializer,
    CourierDeliverySerializer,
    CourierDeliveryStatusUpdateSerializer,
    CourierDetailSerializer,
    CourierFareEstimateRequestSerializer,
    CourierFareEstimateResponseSerializer,
    CourierLocationSerializer,
    CourierPaymentStatusUpdateSerializer,
    CourierProviderListResponseSerializer,
    CourierProviderPublicSerializer,
    CourierProviderStatsSerializer,
    CourierReviewCreateSerializer,
    CourierReviewListResponseSerializer,
    CourierReviewResponseSerializer,
    CourierReviewSerializer,
)
from .services import CourierService


def validation_detail(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'messages'):
        return exc.messages
    return str(exc)


def get_courier_provider_profile(user):
    try:
        return user.courier_provider_profile
    except Exception:
        return None


class PaginatedCourierListMixin:
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = None

    def paginated_response(self, request, queryset, serializer_class=None):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = (serializer_class or self.serializer_class)(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class CourierProviderListView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CourierProviderPublicSerializer

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_list_available_couriers',
        summary='List courier providers accepting dispatch',
        parameters=[
            OpenApiParameter('operating_island_zone', str, required=False),
            OpenApiParameter('transport_mode', str, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: CourierProviderListResponseSerializer},
    )
    def get(self, request):
        queryset = CourierProviderProfile.objects.select_related('user').filter(
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            online_accepting_dispatch=True,
        ).order_by('legal_name', 'business_name')
        zone = (request.query_params.get('operating_island_zone') or '').strip()
        transport_mode = (request.query_params.get('transport_mode') or '').strip()
        if zone:
            queryset = queryset.filter(operating_island_zone__iexact=zone)
        if transport_mode:
            queryset = queryset.filter(transport_mode=transport_mode)
        return self.paginated_response(request, queryset)


class CourierProviderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_retrieve_courier_provider',
        summary='Retrieve an available courier provider',
        responses={200: CourierProviderPublicSerializer, 404: CourierDetailSerializer},
    )
    def get(self, request, pk):
        provider = get_object_or_404(
            CourierProviderProfile.objects.select_related('user'),
            pk=pk,
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            online_accepting_dispatch=True,
        )
        return Response(CourierProviderPublicSerializer(provider, context={'request': request}).data)


class CourierFareEstimateView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_estimate_courier_fare',
        summary='Estimate a courier delivery fare',
        request=CourierFareEstimateRequestSerializer,
        responses={200: CourierFareEstimateResponseSerializer},
    )
    def post(self, request):
        serializer = CourierFareEstimateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fare = CourierService.estimate_fare(
            distance_km=serializer.validated_data.get('distance_km'),
            estimated_duration_minutes=serializer.validated_data.get('estimated_duration_minutes'),
            package_size=serializer.validated_data.get('package_size'),
            transit_insurance=serializer.validated_data.get('transit_insurance'),
        )
        return Response({'estimated_fare': fare, 'currency': 'BSD'})


class CustomerCourierDeliveryListCreateView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CourierDeliverySerializer

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_list_courier_deliveries',
        summary='List my courier deliveries',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in CourierDeliveryStatus], required=False),
            OpenApiParameter('past', bool, required=False, description='When true, returns delivered and cancelled deliveries only.'),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: CourierDeliveryListResponseSerializer},
    )
    def get(self, request):
        queryset = CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user').filter(customer=request.user)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[CourierDeliveryStatus.DELIVERED, CourierDeliveryStatus.CANCELLED])
        return self.paginated_response(request, queryset)

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_create_courier_delivery',
        summary='Book a courier delivery with a selected courier provider',
        request=CourierDeliveryCreateSerializer,
        responses={201: CourierDeliverySerializer, 400: CourierDetailSerializer},
    )
    def post(self, request):
        serializer = CourierDeliveryCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            delivery = serializer.save()
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CourierDeliverySerializer(delivery, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CustomerCourierDeliveryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_retrieve_courier_delivery',
        summary='Retrieve my courier delivery',
        responses={200: CourierDeliverySerializer, 404: CourierDetailSerializer},
    )
    def get(self, request, pk):
        delivery = get_object_or_404(
            CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user'),
            pk=pk,
            customer=request.user,
        )
        return Response(CourierDeliverySerializer(delivery, context={'request': request}).data)


class CustomerCourierDeliveryCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_cancel_courier_delivery',
        summary='Cancel my courier delivery',
        request=CourierDeliveryCancelSerializer,
        responses={200: CourierDeliveryActionResponseSerializer, 400: CourierDetailSerializer, 404: CourierDetailSerializer},
    )
    def post(self, request, pk):
        delivery = get_object_or_404(CourierDelivery, pk=pk, customer=request.user)
        serializer = CourierDeliveryCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = CourierService.cancel_delivery(delivery, request.user, CourierCancellationActor.CUSTOMER, serializer.validated_data.get('reason', ''))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier delivery cancelled.', 'delivery': CourierDeliverySerializer(delivery, context={'request': request}).data})


class CustomerCourierDeliveryReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Courier - Customers'],
        operation_id='customer_review_courier_delivery',
        summary='Review a delivered courier service',
        request=CourierReviewCreateSerializer,
        responses={201: CourierReviewResponseSerializer, 400: CourierDetailSerializer, 404: CourierDetailSerializer},
    )
    def post(self, request, pk):
        delivery = get_object_or_404(CourierDelivery, pk=pk, customer=request.user)
        serializer = CourierReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = CourierService.submit_review(delivery, request.user, serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier review submitted.', 'review': CourierReviewSerializer(review).data}, status=status.HTTP_201_CREATED)


class ProviderCourierRequestListView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = CourierDeliverySerializer

    @extend_schema(
        tags=['Courier - Provider'],
        operation_id='provider_list_available_courier_requests',
        summary='List delivery requests sent to my courier profile',
        parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: CourierDeliveryListResponseSerializer, 403: CourierDetailSerializer},
    )
    def get(self, request):
        profile = get_courier_provider_profile(request.user)
        if not profile or profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            return Response({'detail': 'Completed courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user').filter(
            requested_courier=profile,
            courier__isnull=True,
            status=CourierDeliveryStatus.REQUESTED,
        )
        return self.paginated_response(request, queryset)


class ProviderCourierHistoryView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = CourierDeliverySerializer

    @extend_schema(
        tags=['Courier - Provider'],
        operation_id='provider_list_courier_history',
        summary='List my courier delivery history',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in CourierDeliveryStatus], required=False),
            OpenApiParameter('past', bool, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: CourierDeliveryListResponseSerializer, 403: CourierDetailSerializer},
    )
    def get(self, request):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user').filter(courier=profile)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[CourierDeliveryStatus.DELIVERED, CourierDeliveryStatus.CANCELLED])
        return self.paginated_response(request, queryset)


class ProviderCourierDeliveryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Courier - Provider'], operation_id='provider_retrieve_courier_delivery', summary='Retrieve one of my courier deliveries', responses={200: CourierDeliverySerializer, 403: CourierDetailSerializer, 404: CourierDetailSerializer})
    def get(self, request, pk):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        delivery = get_object_or_404(CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user'), pk=pk, requested_courier=profile)
        return Response(CourierDeliverySerializer(delivery, context={'request': request}).data)


class ProviderCourierAcceptView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Courier - Provider'], operation_id='provider_accept_courier_delivery', summary='Accept a courier delivery request', request=None, responses={200: CourierDeliveryActionResponseSerializer, 400: CourierDetailSerializer, 403: CourierDetailSerializer, 404: CourierDetailSerializer})
    def post(self, request, pk):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        delivery = get_object_or_404(CourierDelivery, pk=pk)
        try:
            delivery = CourierService.accept_delivery(delivery, profile)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier delivery accepted.', 'delivery': CourierDeliverySerializer(delivery, context={'request': request}).data})


class ProviderCourierStatusView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Courier - Provider'],
        operation_id='provider_update_courier_delivery_status',
        summary='Move my courier delivery to the next valid status',
        description='Allowed flow: requested -> assigned -> pickup_arrived -> in_transit -> delivered. cancelled is allowed before delivery.',
        request=CourierDeliveryStatusUpdateSerializer,
        responses={200: CourierDeliveryActionResponseSerializer, 400: CourierDetailSerializer, 403: CourierDetailSerializer, 404: CourierDetailSerializer},
    )
    def post(self, request, pk):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        delivery = get_object_or_404(CourierDelivery, pk=pk, courier=profile)
        serializer = CourierDeliveryStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = CourierService.update_status(delivery, profile, serializer.validated_data['status'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier delivery status updated.', 'delivery': CourierDeliverySerializer(delivery, context={'request': request}).data})


class ProviderCourierLocationView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Courier - Provider'], operation_id='provider_update_courier_location', summary='Update my live location for an assigned courier delivery', request=CourierLocationSerializer, responses={200: CourierDeliveryActionResponseSerializer, 400: CourierDetailSerializer, 403: CourierDetailSerializer, 404: CourierDetailSerializer})
    def post(self, request, pk):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        delivery = get_object_or_404(CourierDelivery, pk=pk, courier=profile)
        serializer = CourierLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = CourierService.update_courier_location(delivery, profile, serializer.validated_data['latitude'], serializer.validated_data['longitude'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier location updated.', 'delivery': CourierDeliverySerializer(delivery, context={'request': request}).data})


class ProviderCourierStatsView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Courier - Provider'], operation_id='provider_retrieve_courier_stats', summary='Retrieve my courier delivery statistics', responses={200: CourierProviderStatsSerializer, 403: CourierDetailSerializer})
    def get(self, request):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(CourierProviderStatsSerializer(CourierService.provider_stats(profile)).data)


class ProviderCourierReviewListView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = CourierReviewSerializer

    @extend_schema(tags=['Courier - Provider'], operation_id='provider_list_courier_reviews', summary='List reviews for my courier profile', parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: CourierReviewListResponseSerializer, 403: CourierDetailSerializer})
    def get(self, request):
        profile = get_courier_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Courier provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CourierReview.objects.select_related('delivery', 'customer', 'courier').filter(courier=profile)
        return self.paginated_response(request, queryset)


class SuperAdminCourierDeliveryListView(PaginatedCourierListMixin, APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = CourierDeliverySerializer

    @extend_schema(tags=['Courier - SuperAdmin'], operation_id='admin_list_courier_deliveries', summary='List all courier deliveries', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in CourierDeliveryStatus], required=False), OpenApiParameter('courier', int, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: CourierDeliveryListResponseSerializer})
    def get(self, request):
        queryset = CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user')
        status_filter = (request.query_params.get('status') or '').strip()
        courier_id = request.query_params.get('courier')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if courier_id:
            queryset = queryset.filter(courier_id=courier_id)
        return self.paginated_response(request, queryset)


class SuperAdminCourierDeliveryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Courier - SuperAdmin'], operation_id='admin_retrieve_courier_delivery', summary='Retrieve a courier delivery', responses={200: CourierDeliverySerializer, 404: CourierDetailSerializer})
    def get(self, request, pk):
        delivery = get_object_or_404(CourierDelivery.objects.select_related('customer', 'requested_courier', 'requested_courier__user', 'courier', 'courier__user'), pk=pk)
        return Response(CourierDeliverySerializer(delivery, context={'request': request}).data)


class SuperAdminCourierPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Courier - SuperAdmin'], operation_id='admin_update_courier_payment_status', summary='Update courier delivery payment status', request=CourierPaymentStatusUpdateSerializer, responses={200: CourierDeliveryActionResponseSerializer, 400: CourierDetailSerializer, 404: CourierDetailSerializer})
    def post(self, request, pk):
        delivery = get_object_or_404(CourierDelivery, pk=pk)
        serializer = CourierPaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            delivery = CourierService.update_payment_status(delivery, serializer.validated_data['payment_status'], final_fare=serializer.validated_data.get('final_fare'))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Courier payment status updated.', 'delivery': CourierDeliverySerializer(delivery, context={'request': request}).data})
