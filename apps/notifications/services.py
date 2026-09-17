import logging
from typing import Iterable

from asgiref.sync import async_to_sync
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.users.models import UserRole
from .models import Notification, NotificationAudience, NotificationPriority, NotificationType

try:
    from channels.layers import get_channel_layer
except ImportError:  # pragma: no cover - dependency guard
    get_channel_layer = None

User = get_user_model()
logger = logging.getLogger(__name__)


SERVICE_LABELS = {
    'rides': 'Ride',
    'restaurants': 'Food order',
    'courier': 'Courier delivery',
    'rentals': 'Rental booking',
    'properties': 'Property booking',
}


def user_audience(user):
    if is_super_admin_user(user):
        return NotificationAudience.SUPER_ADMIN
    if getattr(user, 'role', None) == UserRole.SERVICE_PROVIDER:
        return NotificationAudience.PROVIDER
    return NotificationAudience.CUSTOMER


def is_super_admin_user(user):
    return bool(user and user.is_authenticated and getattr(user, 'is_super_admin', False))


def super_admin_filter():
    return Q(role=UserRole.SUPER_ADMIN) | Q(is_staff=True) | Q(is_superuser=True)


class NotificationService:
    """Create REST notifications for all users and websocket pushes for SuperAdmins only."""

    @staticmethod
    def create_notification(
        user,
        notification_type: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: str = NotificationPriority.NORMAL,
        audience: str | None = None,
        push_websocket: bool | None = None,
    ):
        if not user:
            return None

        notification = Notification.objects.create(
            user=user,
            notification_type=notification_type,
            audience=audience or user_audience(user),
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )

        should_push_ws = is_super_admin_user(user) if push_websocket is None else push_websocket
        if should_push_ws and is_super_admin_user(user):
            transaction.on_commit(lambda: NotificationService._send_websocket(notification))

        return notification

    @staticmethod
    def create_many(
        users: Iterable,
        notification_type: str,
        title: str,
        body: str,
        data: dict | None = None,
        priority: str = NotificationPriority.NORMAL,
        audience: str | None = None,
    ):
        return [
            NotificationService.create_notification(
                user=user,
                notification_type=notification_type,
                title=title,
                body=body,
                data=data,
                priority=priority,
                audience=audience,
            )
            for user in users
            if user
        ]

    @staticmethod
    def notify_superadmins(notification_type, title, body, data=None, priority=NotificationPriority.NORMAL):
        admins = User.objects.filter(super_admin_filter(), is_active=True).distinct()
        return [
            NotificationService.create_notification(
                user=admin,
                notification_type=notification_type,
                audience=NotificationAudience.SUPER_ADMIN,
                title=title,
                body=body,
                data=data or {},
                priority=priority,
                push_websocket=True,
            )
            for admin in admins
        ]

    @staticmethod
    def _send_websocket(notification):
        if get_channel_layer is None:
            logger.warning('Channels is not installed; websocket notification skipped.')
            return False
        try:
            channel_layer = get_channel_layer()
            if channel_layer is None:
                logger.warning('No channel layer configured; websocket notification skipped.')
                return False
            async_to_sync(channel_layer.group_send)(
                f'superadmin_notifications_{notification.user_id}',
                {
                    'type': 'notification.message',
                    'notification_id': str(notification.id),
                    'notification_type': notification.notification_type,
                    'audience': notification.audience,
                    'title': notification.title,
                    'body': notification.body,
                    'data': notification.data,
                    'priority': notification.priority,
                    'created_at': notification.created_at.isoformat(),
                    'unread_count': Notification.objects.filter(user=notification.user, is_read=False).count(),
                },
            )
            return True
        except Exception as exc:  # pragma: no cover - depends on channel backend
            logger.exception('Websocket notification failed for user %s: %s', notification.user_id, exc)
            return False


class NotificationTemplates:
    """Reusable notification templates for platform and service-domain events."""

    @staticmethod
    def welcome_user(user):
        return NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.ACCOUNT,
            title='Welcome to Multi-Service',
            body='Your Multi-Service account is ready.',
            data={'user_id': str(user.id)},
        )

    @staticmethod
    def new_user_registered(user):
        label = getattr(user, 'full_name', '') or getattr(user, 'email', '') or 'A user'
        return NotificationService.notify_superadmins(
            notification_type=NotificationType.NEW_USER,
            title='New user registered',
            body=f'{label} created a Multi-Service account.',
            data={'user_id': str(user.id), 'email': getattr(user, 'email', '')},
        )

    @staticmethod
    def provider_onboarding_submitted(provider_user, service_category, reference_id=None):
        label = getattr(provider_user, 'full_name', '') or getattr(provider_user, 'email', '') or 'A provider'
        service_label = _service_label(service_category)
        return NotificationService.notify_superadmins(
            notification_type=NotificationType.PROVIDER_ONBOARDING_SUBMITTED,
            title=f'{service_label} onboarding submitted',
            body=f'{label} submitted provider onboarding for {service_label.lower()}.',
            data=_payload(service_category, reference_id, provider_user_id=str(provider_user.id)),
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def provider_onboarding_decision(provider_user, service_category, approved, reason=None, reference_id=None):
        service_label = _service_label(service_category)
        notification_type = (
            NotificationType.PROVIDER_ONBOARDING_APPROVED
            if approved else NotificationType.PROVIDER_ONBOARDING_REJECTED
        )
        title = f'{service_label} provider approved' if approved else f'{service_label} provider rejected'
        body = (
            f'Your {service_label.lower()} provider onboarding was approved.'
            if approved else
            f'Your {service_label.lower()} provider onboarding was rejected.'
        )
        if reason:
            body = f'{body} Reason: {reason}'
        return NotificationService.create_notification(
            user=provider_user,
            notification_type=notification_type,
            audience=NotificationAudience.PROVIDER,
            title=title,
            body=body,
            data=_payload(service_category, reference_id, reason=reason),
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def service_request_created(provider_user, service_category, reference_id, customer_user=None):
        service_label = _service_label(service_category)
        return NotificationService.create_notification(
            user=provider_user,
            notification_type=_created_type_for_service(service_category),
            audience=NotificationAudience.PROVIDER,
            title=f'New {service_label.lower()}',
            body=f'You have a new {service_label.lower()} request.',
            data=_payload(service_category, reference_id, customer_user_id=_user_id(customer_user)),
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def service_status_updated(user, service_category, status_label, reference_id, actor=None):
        service_label = _service_label(service_category)
        return NotificationService.create_notification(
            user=user,
            notification_type=_status_type_for_service(service_category),
            title=f'{service_label} status updated',
            body=f'Your {service_label.lower()} status is now {status_label}.',
            data=_payload(service_category, reference_id, status=status_label, actor_user_id=_user_id(actor)),
        )

    @staticmethod
    def payment_status_updated(user, service_category, status_label, reference_id, amount=None, currency=None):
        service_label = _service_label(service_category)
        data = _payload(service_category, reference_id, status=status_label, amount=amount, currency=currency)
        return NotificationService.create_notification(
            user=user,
            notification_type=NotificationType.PAYMENT_STATUS_UPDATED,
            title='Payment status updated',
            body=f'Payment for your {service_label.lower()} is now {status_label}.',
            data=data,
            priority=NotificationPriority.HIGH,
        )

    @staticmethod
    def review_received(provider_user, service_category, reference_id, rating=None):
        service_label = _service_label(service_category)
        body = f'You received a new review for {service_label.lower()}.'
        if rating is not None:
            body = f'{body} Rating: {rating}/5.'
        return NotificationService.create_notification(
            user=provider_user,
            notification_type=NotificationType.REVIEW_RECEIVED,
            audience=NotificationAudience.PROVIDER,
            title='New review received',
            body=body,
            data=_payload(service_category, reference_id, rating=rating),
        )

    @staticmethod
    def system_alert_for_superadmins(title, body, data=None, priority=NotificationPriority.URGENT):
        return NotificationService.notify_superadmins(
            notification_type=NotificationType.SYSTEM_ALERT,
            title=title,
            body=body,
            data=data or {},
            priority=priority,
        )


def _service_label(service_category):
    key = str(service_category or '').strip().lower()
    return SERVICE_LABELS.get(key, key.replace('_', ' ').title() or 'Service')


def _payload(service_category, reference_id=None, **extra):
    data = {'service_category': service_category}
    if reference_id is not None:
        data['reference_id'] = str(reference_id)
    data.update({key: value for key, value in extra.items() if value is not None})
    return data


def _user_id(user):
    return str(user.id) if user else None


def _created_type_for_service(service_category):
    key = str(service_category or '').strip().lower()
    return {
        'rides': NotificationType.RIDE_REQUESTED,
        'restaurants': NotificationType.ORDER_CREATED,
        'courier': NotificationType.COURIER_REQUESTED,
        'rentals': NotificationType.RENTAL_BOOKING_CREATED,
        'properties': NotificationType.PROPERTY_BOOKING_CREATED,
    }.get(key, NotificationType.BOOKING_CREATED)


def _status_type_for_service(service_category):
    key = str(service_category or '').strip().lower()
    return {
        'rides': NotificationType.RIDE_STATUS_UPDATED,
        'restaurants': NotificationType.ORDER_STATUS_UPDATED,
        'courier': NotificationType.COURIER_STATUS_UPDATED,
        'rentals': NotificationType.RENTAL_BOOKING_STATUS_UPDATED,
        'properties': NotificationType.PROPERTY_BOOKING_STATUS_UPDATED,
    }.get(key, NotificationType.BOOKING_STATUS_UPDATED)


def safe_notify(callable_obj, *args, **kwargs):
    """Run a notification hook without breaking the business flow that triggered it."""
    try:
        return callable_obj(*args, **kwargs)
    except Exception as exc:  # pragma: no cover - defensive integration guard
        logger.exception('Notification hook failed: %s', exc)
        return None
