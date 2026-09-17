from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification, NotificationAudience, NotificationPriority, NotificationType
from .serializers import NotificationSerializer, NotificationUnreadCountSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@extend_schema_view(
    list=extend_schema(
        tags=['Notifications'],
        summary='List my notifications',
        description=(
            'Returns REST notifications for the authenticated user. Customers and providers use REST only. '
            'SuperAdmins use the same REST endpoints and may also receive live websocket pushes.'
        ),
        parameters=[
            OpenApiParameter('is_read', bool, required=False, description='Filter by read/unread state.'),
            OpenApiParameter('notification_type', str, enum=[choice.value for choice in NotificationType], required=False),
            OpenApiParameter('audience', str, enum=[choice.value for choice in NotificationAudience], required=False),
            OpenApiParameter('priority', str, enum=[choice.value for choice in NotificationPriority], required=False),
            OpenApiParameter('service_category', str, required=False, description='Filter by data.service_category.'),
            OpenApiParameter('page', int, required=False),
            OpenApiParameter('page_size', int, required=False, description='Items per page, up to 100.'),
        ],
        responses={200: NotificationSerializer(many=True)},
    ),
    retrieve=extend_schema(
        tags=['Notifications'],
        summary='Get my notification details',
        responses={200: NotificationSerializer, 404: OpenApiResponse(description='Notification not found.')},
    ),
)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = NotificationSerializer
    pagination_class = NotificationPagination

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or self.request.user.is_anonymous:
            return Notification.objects.none()

        queryset = Notification.objects.filter(user=self.request.user).order_by('-created_at')

        is_read = self.request.query_params.get('is_read')
        if is_read is not None:
            queryset = queryset.filter(is_read=str(is_read).strip().lower() in ('1', 'true', 'yes'))

        notification_type = (self.request.query_params.get('notification_type') or '').strip()
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)

        audience = (self.request.query_params.get('audience') or '').strip()
        if audience:
            queryset = queryset.filter(audience=audience)

        priority = (self.request.query_params.get('priority') or '').strip()
        if priority:
            queryset = queryset.filter(priority=priority)

        service_category = (self.request.query_params.get('service_category') or '').strip()
        if service_category:
            queryset = queryset.filter(data__service_category=service_category)

        return queryset

    @extend_schema(
        tags=['Notifications'],
        summary='Mark my notification as read',
        responses={200: NotificationSerializer, 404: OpenApiResponse(description='Notification not found.')},
    )
    @action(detail=True, methods=['post'], url_path='mark-read')
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_read()
        return Response(NotificationSerializer(notification).data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Notifications'],
        summary='Mark all my notifications as read',
        responses={200: OpenApiResponse(description='Notifications marked as read.')},
    )
    @action(detail=False, methods=['post'], url_path='mark-all-read')
    def mark_all_read(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now(),
        )
        return Response({'message': f'{count} notification(s) marked as read.', 'updated_count': count})

    @extend_schema(
        tags=['Notifications'],
        summary='Get my unread notification count',
        responses={200: NotificationUnreadCountSerializer},
    )
    @action(detail=False, methods=['get'], url_path='unread-count')
    def unread_count(self, request):
        count = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({'unread_count': count}, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Notifications'],
        summary='Delete my read notifications',
        responses={200: OpenApiResponse(description='Read notifications deleted.')},
    )
    @action(detail=False, methods=['delete'], url_path='clear-read')
    def clear_read(self, request):
        deleted_count, _ = Notification.objects.filter(user=request.user, is_read=True).delete()
        return Response({'deleted_count': deleted_count}, status=status.HTTP_200_OK)
