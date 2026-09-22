from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.providers.models import ProviderOnboardingStatus, RentalProviderProfile
from apps.users.permissions import IsCustomer, IsServiceProvider, IsSuperAdmin
from .models import CarRentalBooking, CarRentalBookingStatus, CarRentalCancellationActor, CarRentalReview, RentalVehicle
from .serializers import (
    CarRentalBookingActionResponseSerializer,
    CarRentalBookingCancelSerializer,
    CarRentalBookingCreateSerializer,
    CarRentalBookingDecisionSerializer,
    CarRentalBookingListResponseSerializer,
    CarRentalBookingSerializer,
    CarRentalDetailSerializer,
    CarRentalPaymentStatusUpdateSerializer,
    CarRentalProviderStatsSerializer,
    CarRentalQuoteRequestSerializer,
    CarRentalQuoteResponseSerializer,
    CarRentalReviewCreateSerializer,
    CarRentalReviewListResponseSerializer,
    CarRentalReviewResponseSerializer,
    CarRentalReviewSerializer,
    RentalProviderListResponseSerializer,
    RentalProviderPublicSerializer,
    RentalVehicleListResponseSerializer,
    RentalVehicleMediaCreateSerializer,
    RentalVehicleMediaSerializer,
    RentalVehicleSerializer,
    RentalVehicleWriteSerializer,
)
from .services import CarRentalService


def validation_detail(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'messages'):
        return exc.messages
    return str(exc)


def get_rental_provider_profile(user):
    try:
        return user.rental_provider_profile
    except Exception:
        return None


class PaginatedCarRentalListMixin:
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = None

    def paginated_response(self, request, queryset, serializer_class=None):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = (serializer_class or self.serializer_class)(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class RentalProviderListView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = RentalProviderPublicSerializer

    @extend_schema(
        tags=['Car Rentals - Customers'],
        operation_id='customer_list_rental_providers',
        summary='List approved car rental providers',
        parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: RentalProviderListResponseSerializer},
    )
    def get(self, request):
        queryset = RentalProviderProfile.objects.select_related('user').filter(
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
        ).order_by('company_or_host_legal_name', 'business_name')
        return self.paginated_response(request, queryset)


class RentalProviderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_retrieve_rental_provider', summary='Retrieve an approved car rental provider', responses={200: RentalProviderPublicSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        provider = get_object_or_404(RentalProviderProfile.objects.select_related('user'), pk=pk, onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True)
        return Response(RentalProviderPublicSerializer(provider, context={'request': request}).data)


class CustomerRentalVehicleListView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = RentalVehicleSerializer

    @extend_schema(
        tags=['Car Rentals - Customers'],
        operation_id='customer_list_rental_vehicles',
        summary='List available rental vehicles',
        parameters=[
            OpenApiParameter('provider', int, required=False),
            OpenApiParameter('category', str, required=False),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
        ],
        responses={200: RentalVehicleListResponseSerializer},
    )
    def get(self, request):
        queryset = RentalVehicle.objects.select_related('provider', 'provider__user').prefetch_related('media').filter(
            provider__onboarding_status=ProviderOnboardingStatus.COMPLETED,
            provider__is_active=True,
            available=True,
        )
        provider_id = request.query_params.get('provider')
        category = (request.query_params.get('category') or '').strip()
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if category:
            queryset = queryset.filter(category=category)
        return self.paginated_response(request, queryset)


class CustomerRentalVehicleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_retrieve_rental_vehicle', summary='Retrieve an available rental vehicle', responses={200: RentalVehicleSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        vehicle = get_object_or_404(
            RentalVehicle.objects.select_related('provider', 'provider__user').prefetch_related('media'),
            pk=pk,
            provider__onboarding_status=ProviderOnboardingStatus.COMPLETED,
            provider__is_active=True,
            available=True,
        )
        return Response(RentalVehicleSerializer(vehicle, context={'request': request}).data)


class CarRentalQuoteView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_quote_car_rental', summary='Quote rental, VAT, escrow, and pre-authorization amounts', request=CarRentalQuoteRequestSerializer, responses={200: CarRentalQuoteResponseSerializer, 400: CarRentalDetailSerializer})
    def post(self, request):
        serializer = CarRentalQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            amounts = CarRentalService.calculate_amounts(serializer.validated_data['vehicle'], serializer.validated_data['start_date'], serializer.validated_data['end_date'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CarRentalQuoteResponseSerializer(amounts).data)


class CustomerCarRentalBookingListCreateView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = CarRentalBookingSerializer

    @extend_schema(
        tags=['Car Rentals - Customers'],
        operation_id='customer_list_car_rental_bookings',
        summary='List my car rental bookings',
        parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in CarRentalBookingStatus], required=False), OpenApiParameter('past', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)],
        responses={200: CarRentalBookingListResponseSerializer},
    )
    def get(self, request):
        queryset = CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle').filter(customer=request.user)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[CarRentalBookingStatus.COMPLETED, CarRentalBookingStatus.CANCELLED, CarRentalBookingStatus.DECLINED])
        return self.paginated_response(request, queryset)

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_create_car_rental_booking', summary='Request a car rental booking', request=CarRentalBookingCreateSerializer, responses={201: CarRentalBookingSerializer, 400: CarRentalDetailSerializer})
    def post(self, request):
        serializer = CarRentalBookingCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            booking = serializer.save()
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CarRentalBookingSerializer(booking, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CustomerCarRentalBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_retrieve_car_rental_booking', summary='Retrieve my car rental booking', responses={200: CarRentalBookingSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        booking = get_object_or_404(CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle'), pk=pk, customer=request.user)
        return Response(CarRentalBookingSerializer(booking, context={'request': request}).data)


class CustomerCarRentalBookingCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_cancel_car_rental_booking', summary='Cancel my car rental booking', request=CarRentalBookingCancelSerializer, responses={200: CarRentalBookingActionResponseSerializer, 400: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(CarRentalBooking, pk=pk, customer=request.user)
        serializer = CarRentalBookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = CarRentalService.cancel_booking(booking, request.user, CarRentalCancellationActor.CUSTOMER, serializer.validated_data.get('reason', ''))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Car rental booking cancelled.', 'booking': CarRentalBookingSerializer(booking, context={'request': request}).data})


class CustomerCarRentalReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Car Rentals - Customers'], operation_id='customer_review_car_rental_booking', summary='Review a completed car rental booking', request=CarRentalReviewCreateSerializer, responses={201: CarRentalReviewResponseSerializer, 400: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(CarRentalBooking, pk=pk, customer=request.user)
        serializer = CarRentalReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = CarRentalService.submit_review(booking, request.user, serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Car rental review submitted.', 'review': CarRentalReviewSerializer(review).data}, status=status.HTTP_201_CREATED)


class ProviderRentalVehicleListCreateView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = RentalVehicleSerializer

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_list_rental_vehicles', summary='List my rental vehicles', parameters=[OpenApiParameter('available', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: RentalVehicleListResponseSerializer, 403: CarRentalDetailSerializer})
    def get(self, request):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = RentalVehicle.objects.prefetch_related('media').filter(provider=provider)
        available = request.query_params.get('available')
        if available is not None:
            queryset = queryset.filter(available=str(available).lower() in ('1', 'true', 'yes'))
        return self.paginated_response(request, queryset)

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_create_rental_vehicle', summary='Create a rental vehicle', request=RentalVehicleWriteSerializer, responses={201: RentalVehicleSerializer, 400: CarRentalDetailSerializer, 403: CarRentalDetailSerializer})
    def post(self, request):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = RentalVehicleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vehicle = serializer.save(provider=provider)
        return Response(RentalVehicleSerializer(vehicle, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ProviderRentalVehicleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    def get_object(self, request, pk):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return None, None, Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return provider, get_object_or_404(RentalVehicle.objects.prefetch_related('media'), pk=pk, provider=provider), None

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_retrieve_rental_vehicle', summary='Retrieve my rental vehicle', responses={200: RentalVehicleSerializer, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        provider, vehicle, error = self.get_object(request, pk)
        if error:
            return error
        return Response(RentalVehicleSerializer(vehicle, context={'request': request}).data)

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_update_rental_vehicle', summary='Patch my rental vehicle', request=RentalVehicleWriteSerializer, responses={200: RentalVehicleSerializer, 400: CarRentalDetailSerializer, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def patch(self, request, pk):
        provider, vehicle, error = self.get_object(request, pk)
        if error:
            return error
        serializer = RentalVehicleWriteSerializer(vehicle, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(RentalVehicleSerializer(serializer.save(), context={'request': request}).data)

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_delete_rental_vehicle', summary='Delete my rental vehicle', responses={204: None, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def delete(self, request, pk):
        provider, vehicle, error = self.get_object(request, pk)
        if error:
            return error
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderRentalVehicleMediaCreateView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_add_rental_vehicle_media', summary='Add a photo to my rental vehicle', request=RentalVehicleMediaCreateSerializer, responses={201: RentalVehicleMediaSerializer, 400: CarRentalDetailSerializer, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def post(self, request, pk):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        vehicle = get_object_or_404(RentalVehicle, pk=pk, provider=provider)
        serializer = RentalVehicleMediaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        media = serializer.save(vehicle=vehicle)
        return Response(RentalVehicleMediaSerializer(media, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ProviderRentalBookingListView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = CarRentalBookingSerializer

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_list_car_rental_bookings', summary='List bookings for my rental provider profile', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in CarRentalBookingStatus], required=False), OpenApiParameter('past', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: CarRentalBookingListResponseSerializer, 403: CarRentalDetailSerializer})
    def get(self, request):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle').filter(provider=provider)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[CarRentalBookingStatus.COMPLETED, CarRentalBookingStatus.CANCELLED, CarRentalBookingStatus.DECLINED])
        return self.paginated_response(request, queryset)


class ProviderRentalBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_retrieve_car_rental_booking', summary='Retrieve a booking for my rental provider profile', responses={200: CarRentalBookingSerializer, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        booking = get_object_or_404(CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle'), pk=pk, provider=provider)
        return Response(CarRentalBookingSerializer(booking, context={'request': request}).data)


class ProviderRentalBookingActionView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    action = None

    @extend_schema(tags=['Car Rentals - Provider'], summary='Perform a provider car rental booking action', request=CarRentalBookingDecisionSerializer, responses={200: CarRentalBookingActionResponseSerializer, 400: CarRentalDetailSerializer, 403: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def post(self, request, pk):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        booking = get_object_or_404(CarRentalBooking, pk=pk, provider=provider)
        serializer = CarRentalBookingDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data.get('note', '')
        try:
            if self.action == 'confirm':
                booking = CarRentalService.confirm_booking(booking, provider, note=note)
                detail = 'Car rental booking confirmed.'
            elif self.action == 'decline':
                booking = CarRentalService.decline_booking(booking, provider, note=note)
                detail = 'Car rental booking declined.'
            elif self.action == 'complete':
                booking = CarRentalService.complete_booking(booking, provider)
                detail = 'Car rental booking completed.'
            else:
                return Response({'detail': 'Unsupported car rental action.'}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail, 'booking': CarRentalBookingSerializer(booking, context={'request': request}).data})


class ProviderRentalBookingConfirmView(ProviderRentalBookingActionView):
    action = 'confirm'


class ProviderRentalBookingDeclineView(ProviderRentalBookingActionView):
    action = 'decline'


class ProviderRentalBookingCompleteView(ProviderRentalBookingActionView):
    action = 'complete'


class ProviderRentalStatsView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_retrieve_car_rental_stats', summary='Retrieve my car rental statistics', responses={200: CarRentalProviderStatsSerializer, 403: CarRentalDetailSerializer})
    def get(self, request):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(CarRentalProviderStatsSerializer(CarRentalService.provider_stats(provider)).data)


class ProviderRentalReviewListView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = CarRentalReviewSerializer

    @extend_schema(tags=['Car Rentals - Provider'], operation_id='provider_list_car_rental_reviews', summary='List reviews for my rental provider profile', parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: CarRentalReviewListResponseSerializer, 403: CarRentalDetailSerializer})
    def get(self, request):
        provider = get_rental_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Rental provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = CarRentalReview.objects.select_related('booking', 'customer', 'provider', 'vehicle').filter(provider=provider)
        return self.paginated_response(request, queryset)


class SuperAdminCarRentalBookingListView(PaginatedCarRentalListMixin, APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = CarRentalBookingSerializer

    @extend_schema(tags=['Car Rentals - SuperAdmin'], operation_id='admin_list_car_rental_bookings', summary='List all car rental bookings', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in CarRentalBookingStatus], required=False), OpenApiParameter('provider', int, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: CarRentalBookingListResponseSerializer})
    def get(self, request):
        queryset = CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle')
        status_filter = (request.query_params.get('status') or '').strip()
        provider_id = request.query_params.get('provider')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        return self.paginated_response(request, queryset)


class SuperAdminCarRentalBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Car Rentals - SuperAdmin'], operation_id='admin_retrieve_car_rental_booking', summary='Retrieve a car rental booking', responses={200: CarRentalBookingSerializer, 404: CarRentalDetailSerializer})
    def get(self, request, pk):
        booking = get_object_or_404(CarRentalBooking.objects.select_related('customer', 'provider', 'provider__user', 'vehicle'), pk=pk)
        return Response(CarRentalBookingSerializer(booking, context={'request': request}).data)


class SuperAdminCarRentalPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Car Rentals - SuperAdmin'], operation_id='admin_update_car_rental_payment_status', summary='Update car rental payment status', request=CarRentalPaymentStatusUpdateSerializer, responses={200: CarRentalBookingActionResponseSerializer, 400: CarRentalDetailSerializer, 404: CarRentalDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(CarRentalBooking, pk=pk)
        serializer = CarRentalPaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = CarRentalService.update_payment_status(booking, serializer.validated_data['payment_status'], total_amount=serializer.validated_data.get('total_amount'))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Car rental payment status updated.', 'booking': CarRentalBookingSerializer(booking, context={'request': request}).data})
