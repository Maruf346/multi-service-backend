from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.http import Http404

from apps.users.permissions import IsSuperAdmin
from .models import (
    PROVIDER_PROFILE_MODELS,
    ProviderApprovalStatus,
    ProviderOnboardingStatus,
    ProviderServiceCategory,
    get_provider_profile_for_user,
)
from .serializers import (
    PROVIDER_SERIALIZERS,
    PROVIDER_WRITE_SERIALIZERS,
    ProviderReviewSerializer,
    ProviderSubmitResponseSerializer,
)
from .services import ProviderProfileService


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

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Get my provider profile for this service type',
        responses={200: OpenApiResponse(description='Provider profile found.'), 404: OpenApiResponse(description='Provider profile not found.')},
    )
    def get(self, request):
        profile = self.get_existing(request.user)
        if not profile:
            return Response({'detail': 'Provider profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        serializer_class = self.get_read_serializer()
        return Response(serializer_class(profile, context={'request': request}).data)

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Create or replace my provider profile for this service type',
        responses={200: OpenApiResponse(description='Provider profile updated.'), 201: OpenApiResponse(description='Provider profile created.')},
    )
    def put(self, request):
        serializer_class = self.get_write_serializer()
        serializer = serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            profile, created = ProviderProfileService.upsert_profile(
                request.user,
                self.get_model_class(),
                serializer.validated_data,
            )
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        read_serializer = self.get_read_serializer()
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(read_serializer(profile, context={'request': request}).data, status=status_code)

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Partially update my provider profile for this service type',
        responses={200: OpenApiResponse(description='Provider profile updated.'), 201: OpenApiResponse(description='Provider profile created.')},
    )
    def patch(self, request):
        existing = self.get_existing(request.user)
        serializer_class = self.get_write_serializer()
        serializer = serializer_class(existing, data=request.data, partial=bool(existing), context={'request': request})
        serializer.is_valid(raise_exception=True)
        try:
            if existing:
                if existing.approval_status == ProviderApprovalStatus.APPROVED:
                    return Response({'detail': 'Approved provider profiles cannot be edited here.'}, status=status.HTTP_400_BAD_REQUEST)
                for field, value in serializer.validated_data.items():
                    setattr(existing, field, value)
                existing.full_clean()
                existing.save(update_fields=[*serializer.validated_data.keys(), 'updated_at'])
                profile = existing
                status_code = status.HTTP_200_OK
            else:
                profile, _ = ProviderProfileService.upsert_profile(
                    request.user,
                    self.get_model_class(),
                    serializer.validated_data,
                )
                status_code = status.HTTP_201_CREATED
        except DjangoValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_400_BAD_REQUEST)
        read_serializer = self.get_read_serializer()
        return Response(read_serializer(profile, context={'request': request}).data, status=status_code)


class ProviderTypedSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    service_category = None

    def get_model_class(self):
        return PROVIDER_PROFILE_MODELS[self.service_category]

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Submit my provider profile for this service type',
        responses={200: ProviderSubmitResponseSerializer, 404: OpenApiResponse(description='Provider profile not found.')},
    )
    def post(self, request):
        model_class = self.get_model_class()
        try:
            profile = model_class.objects.get(user=request.user)
        except model_class.DoesNotExist:
            return Response({'detail': 'Provider profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        if profile.approval_status == ProviderApprovalStatus.APPROVED:
            return Response({'detail': 'Provider profile is already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        profile = ProviderProfileService.submit_for_review(profile)
        serializer_class = PROVIDER_SERIALIZERS[self.service_category]
        return Response({
            'detail': 'Provider profile submitted for review.',
            'provider': serializer_class(profile, context={'request': request}).data,
        })


class RideProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RIDES


class RideProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RIDES


class RestaurantProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RESTAURANTS


class RestaurantProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RESTAURANTS


class CourierProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.COURIER


class CourierProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.COURIER


class RentalProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.RENTALS


class RentalProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.RENTALS


class PropertyProviderProfileView(ProviderTypedProfileView):
    service_category = ProviderServiceCategory.PROPERTIES


class PropertyProviderSubmitView(ProviderTypedSubmitView):
    service_category = ProviderServiceCategory.PROPERTIES


class SuperAdminProviderProfileListView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - Admin'],
        summary='List provider onboarding applications across service types',
        parameters=[
            OpenApiParameter('service_category', str, enum=[choice.value for choice in ProviderServiceCategory], required=False),
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('approval_status', str, enum=[choice.value for choice in ProviderApprovalStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
        ],
        responses={200: OpenApiResponse(description='Provider applications grouped as a flat list.')},
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
            approval_status = (request.query_params.get('approval_status') or '').strip()
            if approval_status:
                queryset = queryset.filter(approval_status=approval_status)
            is_active = request.query_params.get('is_active')
            if is_active is not None:
                queryset = queryset.filter(is_active=str(is_active).strip().lower() in ('1', 'true', 'yes'))
            items.extend(serializer_class(obj, context={'request': request}).data for obj in queryset)
        items.sort(key=lambda item: item.get('created_at') or '', reverse=True)
        return Response(items)


class SuperAdminProviderProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - Admin'],
        summary='Get provider onboarding details by service type',
        responses={200: OpenApiResponse(description='Provider application detail.')},
    )
    def get(self, request, service_category, pk):
        profile, serializer_class = _get_profile_and_serializer(service_category, pk)
        return Response(serializer_class(profile, context={'request': request}).data)


class SuperAdminProviderApproveView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - Admin'],
        summary='Approve provider onboarding by service type',
        request=ProviderReviewSerializer,
        responses={200: OpenApiResponse(description='Provider application approved.')},
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
        tags=['Providers - Admin'],
        summary='Reject provider onboarding by service type',
        request=ProviderReviewSerializer,
        responses={200: OpenApiResponse(description='Provider application rejected.')},
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
