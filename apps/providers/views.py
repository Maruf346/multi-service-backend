from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.shortcuts import get_object_or_404

from apps.users.permissions import IsSuperAdmin
from .models import ProviderApprovalStatus, ProviderOnboardingStatus, ProviderProfile, ProviderServiceCategory
from .serializers import (
    ProviderProfileListSerializer,
    ProviderProfileSerializer,
    ProviderProfileUpsertSerializer,
    ProviderReviewSerializer,
    ProviderSubmitResponseSerializer,
)
from .services import ProviderProfileService


class ProviderProfileMeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Get my provider profile',
        responses={200: ProviderProfileSerializer, 404: OpenApiResponse(description='Provider profile not found.')},
    )
    def get(self, request):
        profile = getattr(request.user, 'provider_profile', None)
        if not profile:
            return Response({'detail': 'Provider profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(ProviderProfileSerializer(profile, context={'request': request}).data)

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Create or replace my provider profile',
        request=ProviderProfileUpsertSerializer,
        responses={200: ProviderProfileSerializer, 201: ProviderProfileSerializer},
    )
    def put(self, request):
        serializer = ProviderProfileUpsertSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        profile, created = ProviderProfileService.upsert_profile(request.user, serializer.validated_data)
        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(ProviderProfileSerializer(profile, context={'request': request}).data, status=status_code)

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Partially update my provider profile',
        request=ProviderProfileUpsertSerializer,
        responses={200: ProviderProfileSerializer, 201: ProviderProfileSerializer},
    )
    def patch(self, request):
        existing = getattr(request.user, 'provider_profile', None)
        serializer = ProviderProfileUpsertSerializer(
            existing,
            data=request.data,
            partial=bool(existing),
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        if existing:
            for field, value in serializer.validated_data.items():
                setattr(existing, field, value)
            existing.save(update_fields=[*serializer.validated_data.keys(), 'updated_at'])
            profile = existing
            status_code = status.HTTP_200_OK
        else:
            profile, _ = ProviderProfileService.upsert_profile(request.user, serializer.validated_data)
            status_code = status.HTTP_201_CREATED
        return Response(ProviderProfileSerializer(profile, context={'request': request}).data, status=status_code)


class ProviderProfileSubmitView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['Providers - Provider'],
        summary='Submit my provider profile for SuperAdmin review',
        responses={200: ProviderSubmitResponseSerializer, 404: OpenApiResponse(description='Provider profile not found.')},
    )
    def post(self, request):
        profile = getattr(request.user, 'provider_profile', None)
        if not profile:
            return Response({'detail': 'Provider profile not found.'}, status=status.HTTP_404_NOT_FOUND)
        if profile.approval_status == ProviderApprovalStatus.APPROVED:
            return Response({'detail': 'Provider profile is already approved.'}, status=status.HTTP_400_BAD_REQUEST)
        profile = ProviderProfileService.submit_for_review(profile)
        return Response({
            'detail': 'Provider profile submitted for review.',
            'provider': ProviderProfileSerializer(profile, context={'request': request}).data,
        })


class SuperAdminProviderProfileListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ProviderProfileListSerializer

    @extend_schema(
        tags=['Providers - Admin'],
        summary='List provider profiles and onboarding applications',
        parameters=[
            OpenApiParameter('service_category', str, enum=[choice.value for choice in ProviderServiceCategory], required=False),
            OpenApiParameter('onboarding_status', str, enum=[choice.value for choice in ProviderOnboardingStatus], required=False),
            OpenApiParameter('approval_status', str, enum=[choice.value for choice in ProviderApprovalStatus], required=False),
            OpenApiParameter('is_active', bool, required=False),
        ],
        responses={200: ProviderProfileListSerializer(many=True)},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        queryset = ProviderProfile.objects.select_related('user', 'reviewed_by').order_by('-created_at')
        service_category = (self.request.query_params.get('service_category') or '').strip()
        if service_category:
            queryset = queryset.filter(service_category=service_category)
        onboarding_status = (self.request.query_params.get('onboarding_status') or '').strip()
        if onboarding_status:
            queryset = queryset.filter(onboarding_status=onboarding_status)
        approval_status = (self.request.query_params.get('approval_status') or '').strip()
        if approval_status:
            queryset = queryset.filter(approval_status=approval_status)
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=str(is_active).strip().lower() in ('1', 'true', 'yes'))
        return queryset


class SuperAdminProviderProfileDetailView(generics.RetrieveAPIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]
    serializer_class = ProviderProfileSerializer
    queryset = ProviderProfile.objects.select_related('user', 'reviewed_by')

    @extend_schema(
        tags=['Providers - Admin'],
        summary='Get provider profile details',
        responses={200: ProviderProfileSerializer, 404: OpenApiResponse(description='Provider profile not found.')},
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class SuperAdminProviderApproveView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - Admin'],
        summary='Approve provider onboarding',
        request=ProviderReviewSerializer,
        responses={200: ProviderProfileSerializer},
    )
    def post(self, request, pk):
        profile = get_object_or_404(ProviderProfile, pk=pk)
        serializer = ProviderReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = ProviderProfileService.approve(profile, reviewer=request.user, note=serializer.validated_data.get('note', ''))
        return Response(ProviderProfileSerializer(profile, context={'request': request}).data)


class SuperAdminProviderRejectView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    @extend_schema(
        tags=['Providers - Admin'],
        summary='Reject provider onboarding',
        request=ProviderReviewSerializer,
        responses={200: ProviderProfileSerializer},
    )
    def post(self, request, pk):
        profile = get_object_or_404(ProviderProfile, pk=pk)
        serializer = ProviderReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = ProviderProfileService.reject(profile, reviewer=request.user, note=serializer.validated_data.get('note', ''))
        return Response(ProviderProfileSerializer(profile, context={'request': request}).data)
