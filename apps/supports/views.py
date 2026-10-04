from django.shortcuts import render
from django.db.models import Q
from rest_framework import viewsets, views
from rest_framework import generics
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from rest_framework import status
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from .serializers import *
from .models import *
import logging
from django.utils.decorators import method_decorator
from apps.notifications.services import NotificationTemplates
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404

from apps.users.permissions import IsSuperAdmin



logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Supports - Customer/Provider'],
    summary="Submit Feedback",
    description="Users (Customer/Provider) can submit feedback about the platform."
)
class SupportTicketCreateView(generics.CreateAPIView):
    """Users (Customer/Provider) submit feedback"""
    serializer_class = SupportTicketCreateSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


@extend_schema(
    tags=['Supports - Customer/Provider'],
    summary="List User Feedback",
    description="Users can view a list of their own feedback submissions."
)
class UserSupportTicketListView(generics.ListAPIView):
    """User can see their own support tickets"""
    serializer_class = SupportTicketCreateSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False):
            return SupportTicket.objects.none()
        return SupportTicket.objects.filter(user=self.request.user)


@extend_schema(
    tags=['Supports - SuperAdmin'],
    summary="Admin Support Ticket Management",
    description="SuperAdmin can list, retrieve, delete, and mark support tickets as resolved. Full update/PUT is intentionally disabled."
)
class SupportTicketAdminViewSet(viewsets.ModelViewSet):
    queryset = SupportTicket.objects.select_related('user').all()
    serializer_class = SupportTicketAdminSerializer
    permission_classes = [IsSuperAdmin]
    http_method_names = ['get', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        queryset = super().get_queryset()
        ticket_status = (self.request.query_params.get('status') or '').strip()
        if ticket_status:
            queryset = queryset.filter(status=ticket_status)
        search = (self.request.query_params.get('search') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search)
                | Q(email__icontains=search)
                | Q(message__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__full_name__icontains=search)
            )
        return queryset

    def get_serializer_class(self):
        if self.action == 'partial_update':
            return SupportTicketStatusUpdateSerializer
        return SupportTicketAdminSerializer

    @extend_schema(
        tags=['Supports - SuperAdmin'],
        summary='List support tickets',
        parameters=[
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False),
            OpenApiParameter('search', str, required=False),
            OpenApiParameter('status', str, enum=[choice.value for choice in SupportTicketStatus], required=False),
        ],
        responses={200: SupportTicketAdminListResponseSerializer},
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=['Supports - SuperAdmin'], summary='Retrieve support ticket', responses={200: SupportTicketAdminSerializer})
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        tags=['Supports - SuperAdmin'],
        summary='Mark support ticket as resolved',
        request=SupportTicketStatusUpdateSerializer,
        responses={200: SupportTicketAdminSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        serializer = SupportTicketStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket.status = serializer.validated_data['status']
        ticket.save(update_fields=['status', 'updated_at'])
        return Response(SupportTicketAdminSerializer(ticket, context={'request': request}).data)