from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.providers.models import ProviderOnboardingStatus
from apps.users.permissions import IsCustomer, IsServiceProvider, IsSuperAdmin
from .models import RideCancellationActor, RideRequest, RideStatus
from .serializers import (
    RideDetailSerializer,
    RideAcceptResponseSerializer,
    RideCancelSerializer,
    RideCreateSerializer,
    RideDriverLocationSerializer,
    RideFareEstimateRequestSerializer,
    RideFareEstimateResponseSerializer,
    RidePaymentStatusUpdateSerializer,
    RideRequestListResponseSerializer,
    RideRequestSerializer,
    RideReviewCreateSerializer,
    RideReviewSerializer,
    RideReviewResponseSerializer,
    RideStatusActionResponseSerializer,
)
from .services import RideService


def validation_detail(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'messages'):
        return exc.messages
    return str(exc)


def get_ride_provider_profile(user):
    try:
        return user.ride_provider_profile
    except Exception:
        return None


class PaginatedRideListMixin:
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def paginated_response(self, request, queryset):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = RideRequestSerializer(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class RideFareEstimateView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_estimate_ride_fare',
        summary='Estimate a ride fare',
        request=RideFareEstimateRequestSerializer,
        responses={200: RideFareEstimateResponseSerializer},
    )
    def post(self, request):
        serializer = RideFareEstimateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        fare = RideService.estimate_fare(
            distance_km=serializer.validated_data.get('distance_km'),
            estimated_duration_minutes=serializer.validated_data.get('estimated_duration_minutes'),
            passenger_count=serializer.validated_data.get('requested_passenger_count'),
        )
        return Response({'estimated_fare': fare, 'currency': 'BSD'})


class CustomerRideListCreateView(PaginatedRideListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_list_rides',
        summary='List my ride requests',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in RideStatus], required=False),
            OpenApiParameter('past', bool, required=False, description='When true, returns completed and cancelled rides only.'),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: RideRequestListResponseSerializer},
    )
    def get(self, request):
        queryset = RideRequest.objects.select_related('customer', 'driver', 'driver__user').filter(customer=request.user).order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[RideStatus.COMPLETED, RideStatus.CANCELLED])
        return self.paginated_response(request, queryset)

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_create_ride',
        summary='Request a Swift ride',
        request=RideCreateSerializer,
        responses={201: RideRequestSerializer, 400: RideDetailSerializer},
    )
    def post(self, request):
        serializer = RideCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        ride = serializer.save()
        return Response(RideRequestSerializer(ride, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CustomerRideDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    def get_object(self, request, pk):
        return get_object_or_404(
            RideRequest.objects.select_related('customer', 'driver', 'driver__user'),
            pk=pk,
            customer=request.user,
        )

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_retrieve_ride',
        summary='Retrieve my ride request',
        responses={200: RideRequestSerializer, 404: RideDetailSerializer},
    )
    def get(self, request, pk):
        return Response(RideRequestSerializer(self.get_object(request, pk), context={'request': request}).data)


class CustomerRideCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_cancel_ride',
        summary='Cancel my ride request',
        request=RideCancelSerializer,
        responses={200: RideStatusActionResponseSerializer, 400: RideDetailSerializer, 404: RideDetailSerializer},
    )
    def post(self, request, pk):
        ride = get_object_or_404(RideRequest, pk=pk, customer=request.user)
        serializer = RideCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ride = RideService.cancel_ride(
                ride=ride,
                actor=request.user,
                actor_type=RideCancellationActor.CUSTOMER,
                reason=serializer.validated_data.get('reason', ''),
            )
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Ride cancelled.', 'ride': RideRequestSerializer(ride, context={'request': request}).data})


class CustomerRideReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(
        tags=['Rides - Customers'],
        operation_id='customer_review_ride',
        summary='Review a completed ride',
        request=RideReviewCreateSerializer,
        responses={201: RideReviewResponseSerializer, 400: RideDetailSerializer, 404: RideDetailSerializer},
    )
    def post(self, request, pk):
        ride = get_object_or_404(RideRequest, pk=pk, customer=request.user)
        serializer = RideReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = RideService.submit_review(ride, request.user, serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Ride review submitted.', 'review': RideReviewSerializer(review).data}, status=status.HTTP_201_CREATED)


class ProviderAvailableRideListView(PaginatedRideListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Rides - Provider'],
        operation_id='provider_list_available_rides',
        summary='List ride requests available to my driver profile',
        parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: RideRequestListResponseSerializer, 403: RideDetailSerializer},
    )
    def get(self, request):
        profile = get_ride_provider_profile(request.user)
        if not profile or profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            return Response({'detail': 'Completed ride provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = RideRequest.objects.select_related('customer', 'driver', 'driver__user').filter(
            status=RideStatus.MATCHING,
            driver__isnull=True,
            requested_passenger_count__lte=profile.seat_capacity or 0,
        ).order_by('-created_at')
        if profile.vehicle_category:
            queryset = queryset.filter(requested_vehicle_category__in=['', profile.vehicle_category])
        return self.paginated_response(request, queryset)


class ProviderRideHistoryView(PaginatedRideListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Rides - Provider'],
        operation_id='provider_list_ride_history',
        summary='List my assigned ride history',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in RideStatus], required=False),
            OpenApiParameter('past', bool, required=False, description='When true, returns completed and cancelled rides only.'),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: RideRequestListResponseSerializer, 403: RideDetailSerializer},
    )
    def get(self, request):
        profile = get_ride_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Ride provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = RideRequest.objects.select_related('customer', 'driver', 'driver__user').filter(driver=profile).order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[RideStatus.COMPLETED, RideStatus.CANCELLED])
        return self.paginated_response(request, queryset)


class ProviderRideActionView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = RideStatusActionResponseSerializer
    action = None

    def get_profile(self):
        return get_ride_provider_profile(self.request.user)

    @extend_schema(
        tags=['Rides - Provider'],
        summary='Perform a provider ride action',
        request=None,
        responses={200: RideStatusActionResponseSerializer, 400: RideDetailSerializer, 403: RideDetailSerializer, 404: RideDetailSerializer},
    )
    def post(self, request, pk):
        profile = self.get_profile()
        if not profile:
            return Response({'detail': 'Ride provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        ride = get_object_or_404(RideRequest, pk=pk)
        try:
            if self.action == 'accept':
                ride = RideService.accept_ride(ride, profile)
                detail = 'Ride accepted.'
            elif self.action == 'arrived':
                ride = RideService.mark_arrived(ride, profile)
                detail = 'Ride marked as arrived.'
            elif self.action == 'start':
                ride = RideService.start_ride(ride, profile)
                detail = 'Ride started.'
            elif self.action == 'complete':
                ride = RideService.complete_ride(ride, profile)
                detail = 'Ride completed.'
            else:
                return Response({'detail': 'Unsupported ride action.'}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail, 'ride': RideRequestSerializer(ride, context={'request': request}).data})


class ProviderRideAcceptView(ProviderRideActionView):
    action = 'accept'


class ProviderRideArrivedView(ProviderRideActionView):
    action = 'arrived'


class ProviderRideStartView(ProviderRideActionView):
    action = 'start'


class ProviderRideCompleteView(ProviderRideActionView):
    action = 'complete'


class ProviderRideLocationUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(
        tags=['Rides - Provider'],
        operation_id='provider_update_ride_location',
        summary='Update my live location for an assigned ride',
        request=RideDriverLocationSerializer,
        responses={200: RideStatusActionResponseSerializer, 400: RideDetailSerializer, 403: RideDetailSerializer, 404: RideDetailSerializer},
    )
    def post(self, request, pk):
        profile = get_ride_provider_profile(request.user)
        if not profile:
            return Response({'detail': 'Ride provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        ride = get_object_or_404(RideRequest, pk=pk, driver=profile)
        if ride.status not in (RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS):
            return Response({'detail': 'Driver location can only be updated for active assigned rides.'}, status=status.HTTP_400_BAD_REQUEST)
        serializer = RideDriverLocationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ride = RideService.update_driver_location(ride, profile, serializer.validated_data['latitude'], serializer.validated_data['longitude'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Driver location updated.', 'ride': RideRequestSerializer(ride, context={'request': request}).data})


class SuperAdminRideListView(PaginatedRideListMixin, APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Rides - SuperAdmin'],
        operation_id='admin_list_rides',
        summary='List all ride requests',
        parameters=[
            OpenApiParameter('status', str, enum=[choice.value for choice in RideStatus], required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: RideRequestListResponseSerializer},
    )
    def get(self, request):
        queryset = RideRequest.objects.select_related('customer', 'driver', 'driver__user').order_by('-created_at')
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        return self.paginated_response(request, queryset)


class SuperAdminRideDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Rides - SuperAdmin'],
        operation_id='admin_retrieve_ride',
        summary='Retrieve a ride request',
        responses={200: RideRequestSerializer, 404: RideDetailSerializer},
    )
    def get(self, request, pk):
        ride = get_object_or_404(RideRequest.objects.select_related('customer', 'driver', 'driver__user'), pk=pk)
        return Response(RideRequestSerializer(ride, context={'request': request}).data)


class SuperAdminRidePaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Rides - SuperAdmin'],
        operation_id='admin_update_ride_payment_status',
        summary='Update ride payment status',
        request=RidePaymentStatusUpdateSerializer,
        responses={200: RideStatusActionResponseSerializer, 400: RideDetailSerializer, 404: RideDetailSerializer},
    )
    def post(self, request, pk):
        ride = get_object_or_404(RideRequest, pk=pk)
        serializer = RidePaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ride = RideService.update_payment_status(
                ride,
                serializer.validated_data['payment_status'],
                final_fare=serializer.validated_data.get('final_fare'),
            )
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Ride payment status updated.', 'ride': RideRequestSerializer(ride, context={'request': request}).data})
