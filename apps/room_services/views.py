from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from apps.providers.models import PropertyProviderProfile, ProviderOnboardingStatus
from apps.users.permissions import IsCustomer, IsServiceProvider, IsSuperAdmin
from .models import PropertyAvailability, PropertyListing, PropertyListingPhoto, RoomBooking, RoomBookingStatus, RoomCancellationActor, RoomReview
from .serializers import *
from .services import RoomService


def validation_detail(exc):
    if hasattr(exc, 'message_dict'):
        return exc.message_dict
    if hasattr(exc, 'messages'):
        return exc.messages
    return str(exc)


def get_property_provider_profile(user):
    try:
        return user.property_provider_profile
    except Exception:
        return None


class PaginatedRoomListMixin:
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = None

    def paginated_response(self, request, queryset, serializer_class=None):
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        serializer = (serializer_class or self.serializer_class)(page, many=True, context={'request': request})
        return paginator.get_paginated_response(serializer.data)


class PropertyProviderListView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = PropertyProviderPublicSerializer

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_list_property_providers', summary='List approved room/property providers', parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: PropertyProviderListResponseSerializer})
    def get(self, request):
        queryset = PropertyProviderProfile.objects.select_related('user').filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True)
        return self.paginated_response(request, queryset)


class PropertyProviderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_retrieve_property_provider', summary='Retrieve an approved room/property provider', responses={200: PropertyProviderPublicSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        provider = get_object_or_404(PropertyProviderProfile.objects.select_related('user'), pk=pk, onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True)
        return Response(PropertyProviderPublicSerializer(provider, context={'request': request}).data)


class CustomerPropertyListingListView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = PropertyListingSerializer

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_list_property_listings', summary='List active room/property listings', parameters=[OpenApiParameter('provider', int, required=False), OpenApiParameter('island_region', str, required=False), OpenApiParameter('guests', int, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: PropertyListingListResponseSerializer})
    def get(self, request):
        queryset = PropertyListing.objects.select_related('provider', 'provider__user').prefetch_related('photos').filter(provider__onboarding_status=ProviderOnboardingStatus.COMPLETED, provider__is_active=True, is_active=True)
        provider_id = request.query_params.get('provider')
        island = (request.query_params.get('island_region') or '').strip()
        guests = request.query_params.get('guests')
        if provider_id:
            queryset = queryset.filter(provider_id=provider_id)
        if island:
            queryset = queryset.filter(island_region__iexact=island)
        if guests:
            queryset = queryset.filter(max_guests__gte=guests)
        return self.paginated_response(request, queryset)


class CustomerPropertyListingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_retrieve_property_listing', summary='Retrieve an active room/property listing', responses={200: PropertyListingSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        listing = get_object_or_404(PropertyListing.objects.select_related('provider', 'provider__user').prefetch_related('photos'), pk=pk, provider__onboarding_status=ProviderOnboardingStatus.COMPLETED, provider__is_active=True, is_active=True)
        return Response(PropertyListingSerializer(listing, context={'request': request}).data)


class RoomQuoteView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_quote_room_booking', summary='Quote room/property booking total', request=RoomQuoteRequestSerializer, responses={200: RoomQuoteResponseSerializer, 400: RoomDetailSerializer})
    def post(self, request):
        serializer = RoomQuoteRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RoomService.validate_listing_available(serializer.validated_data['listing'], serializer.validated_data['check_in_date'], serializer.validated_data['check_out_date'], serializer.validated_data['number_of_persons'])
            quote = RoomService.quote(serializer.validated_data['listing'], serializer.validated_data['check_in_date'], serializer.validated_data['check_out_date'])
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RoomQuoteResponseSerializer(quote).data)


class CustomerRoomBookingListCreateView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsCustomer]
    serializer_class = RoomBookingSerializer

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_list_room_bookings', summary='List my room/property bookings', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in RoomBookingStatus], required=False), OpenApiParameter('past', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: RoomBookingListResponseSerializer})
    def get(self, request):
        queryset = RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing').filter(customer=request.user)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[RoomBookingStatus.COMPLETED, RoomBookingStatus.CANCELLED, RoomBookingStatus.DECLINED])
        return self.paginated_response(request, queryset)

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_create_room_booking', summary='Request a room/property booking', request=RoomBookingCreateSerializer, responses={201: RoomBookingSerializer, 400: RoomDetailSerializer})
    def post(self, request):
        serializer = RoomBookingCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            booking = serializer.save()
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(RoomBookingSerializer(booking, context={'request': request}).data, status=status.HTTP_201_CREATED)


class CustomerRoomBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_retrieve_room_booking', summary='Retrieve my room/property booking', responses={200: RoomBookingSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        booking = get_object_or_404(RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing'), pk=pk, customer=request.user)
        return Response(RoomBookingSerializer(booking, context={'request': request}).data)


class CustomerRoomBookingCancelView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_cancel_room_booking', summary='Cancel my room/property booking', request=RoomBookingCancelSerializer, responses={200: RoomBookingActionResponseSerializer, 400: RoomDetailSerializer, 404: RoomDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(RoomBooking, pk=pk, customer=request.user)
        serializer = RoomBookingCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = RoomService.cancel_booking(booking, request.user, RoomCancellationActor.CUSTOMER, serializer.validated_data.get('reason', ''))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Room booking cancelled.', 'booking': RoomBookingSerializer(booking, context={'request': request}).data})


class CustomerRoomReviewView(APIView):
    permission_classes = [IsAuthenticated, IsCustomer]

    @extend_schema(tags=['Room Services - Customers'], operation_id='customer_review_room_booking', summary='Review a completed room/property booking', request=RoomReviewCreateSerializer, responses={201: RoomReviewResponseSerializer, 400: RoomDetailSerializer, 404: RoomDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(RoomBooking, pk=pk, customer=request.user)
        serializer = RoomReviewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            review = RoomService.submit_review(booking, request.user, serializer.validated_data)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Room review submitted.', 'review': RoomReviewSerializer(review).data}, status=status.HTTP_201_CREATED)


class ProviderListingListCreateView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = PropertyListingSerializer

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_list_property_listings', summary='List my property listings', parameters=[OpenApiParameter('is_active', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: PropertyListingListResponseSerializer, 403: RoomDetailSerializer})
    def get(self, request):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = PropertyListing.objects.prefetch_related('photos').filter(provider=provider)
        active = request.query_params.get('is_active')
        if active is not None:
            queryset = queryset.filter(is_active=str(active).lower() in ('1', 'true', 'yes'))
        return self.paginated_response(request, queryset)

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_create_property_listing', summary='Create a property listing', request=PropertyListingWriteSerializer, responses={201: PropertyListingSerializer, 400: RoomDetailSerializer, 403: RoomDetailSerializer})
    def post(self, request):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PropertyListingWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        listing = serializer.save(provider=provider)
        return Response(PropertyListingSerializer(listing, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ProviderListingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    def get_object(self, request, pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return None, None, Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return provider, get_object_or_404(PropertyListing.objects.prefetch_related('photos'), pk=pk, provider=provider), None

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_retrieve_property_listing', summary='Retrieve my property listing', responses={200: PropertyListingSerializer, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        provider, listing, error = self.get_object(request, pk)
        if error:
            return error
        return Response(PropertyListingSerializer(listing, context={'request': request}).data)

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_update_property_listing', summary='Patch my property listing', request=PropertyListingWriteSerializer, responses={200: PropertyListingSerializer, 400: RoomDetailSerializer, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def patch(self, request, pk):
        provider, listing, error = self.get_object(request, pk)
        if error:
            return error
        serializer = PropertyListingWriteSerializer(listing, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PropertyListingSerializer(serializer.save(), context={'request': request}).data)

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_delete_property_listing', summary='Delete my property listing', responses={204: None, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def delete(self, request, pk):
        provider, listing, error = self.get_object(request, pk)
        if error:
            return error
        listing.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderListingPhotoCreateView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_add_property_listing_photo', summary='Add a photo to my property listing', request=PropertyListingPhotoCreateSerializer, responses={201: PropertyListingPhotoSerializer, 400: RoomDetailSerializer, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def post(self, request, pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        listing = get_object_or_404(PropertyListing, pk=pk, provider=provider)
        serializer = PropertyListingPhotoCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        photo = serializer.save(listing=listing)
        if photo.is_cover:
            PropertyListingPhoto.objects.filter(listing=listing).exclude(pk=photo.pk).update(is_cover=False)
        return Response(PropertyListingPhotoSerializer(photo, context={'request': request}).data, status=status.HTTP_201_CREATED)


class ProviderAvailabilityListCreateView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = PropertyAvailabilitySerializer

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_list_property_availability', summary='List datewise availability for my listing', parameters=[OpenApiParameter('date_from', str, required=False), OpenApiParameter('date_to', str, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: PropertyAvailabilitySerializer(many=True), 403: RoomDetailSerializer})
    def get(self, request, listing_pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        listing = get_object_or_404(PropertyListing, pk=listing_pk, provider=provider)
        queryset = PropertyAvailability.objects.filter(listing=listing)
        if request.query_params.get('date_from'):
            queryset = queryset.filter(date__gte=request.query_params['date_from'])
        if request.query_params.get('date_to'):
            queryset = queryset.filter(date__lte=request.query_params['date_to'])
        return self.paginated_response(request, queryset)

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_create_property_availability', summary='Create/update datewise availability for my listing', request=PropertyAvailabilityWriteSerializer, responses={201: PropertyAvailabilitySerializer, 400: RoomDetailSerializer, 403: RoomDetailSerializer})
    def post(self, request, listing_pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        listing = get_object_or_404(PropertyListing, pk=listing_pk, provider=provider)
        serializer = PropertyAvailabilityWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        availability, _ = PropertyAvailability.objects.update_or_create(listing=listing, date=serializer.validated_data['date'], defaults={k: v for k, v in serializer.validated_data.items() if k != 'date'})
        return Response(PropertyAvailabilitySerializer(availability).data, status=status.HTTP_201_CREATED)


class ProviderBookingListView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = RoomBookingSerializer

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_list_room_bookings', summary='List bookings for my property provider profile', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in RoomBookingStatus], required=False), OpenApiParameter('past', bool, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: RoomBookingListResponseSerializer, 403: RoomDetailSerializer})
    def get(self, request):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing').filter(provider=provider)
        status_filter = (request.query_params.get('status') or '').strip()
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if str(request.query_params.get('past', '')).lower() in ('1', 'true', 'yes'):
            queryset = queryset.filter(status__in=[RoomBookingStatus.COMPLETED, RoomBookingStatus.CANCELLED, RoomBookingStatus.DECLINED])
        return self.paginated_response(request, queryset)


class ProviderBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_retrieve_room_booking', summary='Retrieve a booking for my provider profile', responses={200: RoomBookingSerializer, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        booking = get_object_or_404(RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing'), pk=pk, provider=provider)
        return Response(RoomBookingSerializer(booking, context={'request': request}).data)


class ProviderBookingActionView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    action = None

    @extend_schema(tags=['Room Services - Provider'], summary='Perform a provider room booking action', request=RoomBookingDecisionSerializer, responses={200: RoomBookingActionResponseSerializer, 400: RoomDetailSerializer, 403: RoomDetailSerializer, 404: RoomDetailSerializer})
    def post(self, request, pk):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        booking = get_object_or_404(RoomBooking, pk=pk, provider=provider)
        serializer = RoomBookingDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.validated_data.get('note', '')
        try:
            if self.action == 'confirm':
                booking = RoomService.confirm_booking(booking, provider, note=note)
                detail = 'Room booking confirmed.'
            elif self.action == 'decline':
                booking = RoomService.decline_booking(booking, provider, note=note)
                detail = 'Room booking declined.'
            elif self.action == 'complete':
                booking = RoomService.complete_booking(booking, provider)
                detail = 'Room booking completed.'
            else:
                return Response({'detail': 'Unsupported room booking action.'}, status=status.HTTP_400_BAD_REQUEST)
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': detail, 'booking': RoomBookingSerializer(booking, context={'request': request}).data})


class ProviderBookingConfirmView(ProviderBookingActionView):
    action = 'confirm'


class ProviderBookingDeclineView(ProviderBookingActionView):
    action = 'decline'


class ProviderBookingCompleteView(ProviderBookingActionView):
    action = 'complete'


class ProviderRoomStatsView(APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_retrieve_room_stats', summary='Retrieve my room/property statistics', responses={200: RoomProviderStatsSerializer, 403: RoomDetailSerializer})
    def get(self, request):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(RoomProviderStatsSerializer(RoomService.provider_stats(provider)).data)


class ProviderRoomReviewListView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsServiceProvider]
    serializer_class = RoomReviewSerializer

    @extend_schema(tags=['Room Services - Provider'], operation_id='provider_list_room_reviews', summary='List reviews for my property provider profile', parameters=[OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: RoomReviewListResponseSerializer, 403: RoomDetailSerializer})
    def get(self, request):
        provider = get_property_provider_profile(request.user)
        if not provider:
            return Response({'detail': 'Property provider profile is required.'}, status=status.HTTP_403_FORBIDDEN)
        queryset = RoomReview.objects.select_related('booking', 'customer', 'provider', 'listing').filter(provider=provider)
        return self.paginated_response(request, queryset)


class SuperAdminRoomBookingListView(PaginatedRoomListMixin, APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = RoomBookingSerializer

    @extend_schema(tags=['Room Services - SuperAdmin'], operation_id='admin_list_room_bookings', summary='List all room/property bookings', parameters=[OpenApiParameter('status', str, enum=[choice.value for choice in RoomBookingStatus], required=False), OpenApiParameter('provider', int, required=False), OpenApiParameter('page', int, required=False), OpenApiParameter('page_size', int, required=False)], responses={200: RoomBookingListResponseSerializer})
    def get(self, request):
        queryset = RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing')
        if request.query_params.get('status'):
            queryset = queryset.filter(status=request.query_params['status'])
        if request.query_params.get('provider'):
            queryset = queryset.filter(provider_id=request.query_params['provider'])
        return self.paginated_response(request, queryset)


class SuperAdminRoomBookingDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Room Services - SuperAdmin'], operation_id='admin_retrieve_room_booking', summary='Retrieve a room/property booking', responses={200: RoomBookingSerializer, 404: RoomDetailSerializer})
    def get(self, request, pk):
        booking = get_object_or_404(RoomBooking.objects.select_related('customer', 'provider', 'provider__user', 'listing'), pk=pk)
        return Response(RoomBookingSerializer(booking, context={'request': request}).data)


class SuperAdminRoomPaymentStatusView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(tags=['Room Services - SuperAdmin'], operation_id='admin_update_room_payment_status', summary='Update room booking payment status', request=RoomPaymentStatusUpdateSerializer, responses={200: RoomBookingActionResponseSerializer, 400: RoomDetailSerializer, 404: RoomDetailSerializer})
    def post(self, request, pk):
        booking = get_object_or_404(RoomBooking, pk=pk)
        serializer = RoomPaymentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            booking = RoomService.update_payment_status(booking, serializer.validated_data['payment_status'], total_amount=serializer.validated_data.get('total_amount'))
        except DjangoValidationError as exc:
            return Response({'detail': validation_detail(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response({'detail': 'Room payment status updated.', 'booking': RoomBookingSerializer(booking, context={'request': request}).data})
