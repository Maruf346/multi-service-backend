from django.shortcuts import render
from rest_framework import viewsets, views
from rest_framework import generics
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from rest_framework import status
from drf_spectacular.utils import extend_schema, extend_schema_view
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
        return SupportTicket.objects.filter(user=self.request.user)


@extend_schema(
    tags=['Supports - SuperAdmin'],
    summary="Admin Support Ticket Management",
    description="Admin can view, update, or delete all support ticket submissions from users."
)
class SupportTicketAdminViewSet(viewsets.ModelViewSet):
    """Admin can CRUD all support tickets"""
    queryset = SupportTicket.objects.all()
    serializer_class = SupportTicketAdminSerializer
    permission_classes = [IsSuperAdmin]