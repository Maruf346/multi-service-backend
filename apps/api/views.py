from django.contrib.auth import get_user_model
from django.db.models import Sum
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import (
    CourierProviderProfile,
    PropertyProviderProfile,
    ProviderOnboardingStatus,
    RentalProviderProfile,
    RestaurantProviderProfile,
    RideProviderProfile,
)
from apps.supports.models import SupportTicket, SupportTicketStatus
from apps.users.models import UserRole
from apps.users.permissions import IsSuperAdmin


DashboardSummarySerializer = inline_serializer(
    name='AdminDashboardSummary',
    fields={
        'pending_provider_registrations': serializers.IntegerField(),
        'active_accounts': serializers.IntegerField(),
        'total_registered_users': serializers.IntegerField(),
        'customers': serializers.IntegerField(),
        'drivers': serializers.IntegerField(),
        'food_vendors': serializers.IntegerField(),
        'couriers': serializers.IntegerField(),
        'car_rentals': serializers.IntegerField(),
        'properties': serializers.IntegerField(),
        'support_tickets': serializers.IntegerField(),
        'new_support_tickets': serializers.IntegerField(),
    },
)


@extend_schema(
    tags=['Dashboard - SuperAdmin'],
    summary='Retrieve SuperAdmin dashboard summary',
    responses={200: DashboardSummarySerializer},
)
class AdminDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsSuperAdmin]

    def get(self, request):
        User = get_user_model()
        provider_models = [
            RideProviderProfile,
            RestaurantProviderProfile,
            CourierProviderProfile,
            RentalProviderProfile,
            PropertyProviderProfile,
        ]
        pending_provider_registrations = sum(
            model.objects.filter(onboarding_status=ProviderOnboardingStatus.SUBMITTED).count()
            for model in provider_models
        )

        return Response({
            'pending_provider_registrations': pending_provider_registrations,
            'active_accounts': User.objects.filter(is_active=True).count(),
            'total_registered_users': User.objects.count(),
            'customers': User.objects.filter(role=UserRole.CUSTOMER).count(),
            'drivers': RideProviderProfile.objects.filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True).count(),
            'food_vendors': RestaurantProviderProfile.objects.filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True).count(),
            'couriers': CourierProviderProfile.objects.filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True).count(),
            'car_rentals': RentalProviderProfile.objects.filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True).count(),
            'properties': PropertyProviderProfile.objects.filter(onboarding_status=ProviderOnboardingStatus.COMPLETED, is_active=True).count(),
            'support_tickets': SupportTicket.objects.count(),
            'new_support_tickets': SupportTicket.objects.filter(status=SupportTicketStatus.PENDING).count(),
        })
