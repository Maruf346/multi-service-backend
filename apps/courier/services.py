import random
from decimal import Decimal, ROUND_HALF_UP

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.providers.models import ProviderOnboardingStatus, ProviderServiceCategory
from .consumers import courier_delivery_tracking_group_name
from .models import (
    CourierCancellationActor,
    CourierDelivery,
    CourierDeliveryStatus,
    CourierPackageSize,
    CourierPaymentMethod,
    CourierPaymentStatus,
    CourierReview,
)

BASE_FARE = Decimal('7.00')
PER_KM_RATE = Decimal('1.85')
PER_MINUTE_RATE = Decimal('0.40')
INSURANCE_FEE = Decimal('5.00')
MINIMUM_FARE = Decimal('10.00')
PACKAGE_SURCHARGES = {
    CourierPackageSize.DOCUMENT: Decimal('0.00'),
    CourierPackageSize.SMALL_PARCEL: Decimal('2.00'),
    CourierPackageSize.MEDIUM_BOX: Decimal('5.00'),
    CourierPackageSize.LARGE_CARGO: Decimal('12.00'),
}

STATUS_TIMESTAMPS = {
    CourierDeliveryStatus.ASSIGNED: 'assigned_at',
    CourierDeliveryStatus.PICKUP_ARRIVED: 'pickup_arrived_at',
    CourierDeliveryStatus.IN_TRANSIT: 'in_transit_at',
    CourierDeliveryStatus.DELIVERED: 'delivered_at',
}

ALLOWED_TRANSITIONS = {
    CourierDeliveryStatus.REQUESTED: {CourierDeliveryStatus.ASSIGNED, CourierDeliveryStatus.CANCELLED},
    CourierDeliveryStatus.ASSIGNED: {CourierDeliveryStatus.PICKUP_ARRIVED, CourierDeliveryStatus.CANCELLED},
    CourierDeliveryStatus.PICKUP_ARRIVED: {CourierDeliveryStatus.IN_TRANSIT, CourierDeliveryStatus.CANCELLED},
    CourierDeliveryStatus.IN_TRANSIT: {CourierDeliveryStatus.DELIVERED, CourierDeliveryStatus.CANCELLED},
}


class CourierService:
    @staticmethod
    def estimate_fare(distance_km=None, estimated_duration_minutes=None, package_size=CourierPackageSize.SMALL_PARCEL, transit_insurance=False):
        distance = Decimal(str(distance_km or '0'))
        duration = Decimal(str(estimated_duration_minutes or '0'))
        surcharge = PACKAGE_SURCHARGES.get(package_size, Decimal('0.00'))
        fare = BASE_FARE + (distance * PER_KM_RATE) + (duration * PER_MINUTE_RATE) + surcharge
        if transit_insurance:
            fare += INSURANCE_FEE
        fare = max(fare, MINIMUM_FARE)
        return fare.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    def validate_courier_can_receive(courier_profile):
        if not courier_profile:
            raise ValidationError('Courier provider profile not found.')
        if courier_profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Courier onboarding must be completed before receiving delivery requests.')
        if not courier_profile.is_active or not courier_profile.online_accepting_dispatch:
            raise ValidationError('Courier is not online and accepting dispatch right now.')

    @staticmethod
    @transaction.atomic
    def create_delivery(customer, data):
        courier_profile = data['requested_courier']
        CourierService.validate_courier_can_receive(courier_profile)
        transit_insurance = data.get('transit_insurance', False)
        data['transit_insurance_amount'] = INSURANCE_FEE if transit_insurance else Decimal('0.00')
        data['estimated_fare'] = data.get('estimated_fare') or CourierService.estimate_fare(
            data.get('distance_km'),
            data.get('estimated_duration_minutes'),
            data.get('package_size'),
            transit_insurance,
        )
        if data.get('payment_method') == CourierPaymentMethod.CASH_ON_DELIVERY:
            data['payment_status'] = CourierPaymentStatus.CASH_DUE
        else:
            data['payment_status'] = CourierPaymentStatus.PENDING
        data['pickup_handover_pin'] = CourierService.generate_pickup_pin()
        delivery = CourierDelivery.objects.create(customer=customer, **data)
        safe_notify(
            NotificationTemplates.service_request_created,
            courier_profile.user,
            ProviderServiceCategory.COURIER,
            delivery.id,
            customer_user=customer,
        )
        CourierService.broadcast_status(delivery, 'Courier delivery requested.', actor_user=customer)
        return delivery

    @staticmethod
    def generate_pickup_pin():
        return f'{random.randint(0, 9999):04d}'

    @staticmethod
    @transaction.atomic
    def accept_delivery(delivery, courier_profile):
        delivery = CourierDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.requested_courier_id != courier_profile.id:
            raise ValidationError('This delivery request was not sent to your courier profile.')
        CourierService.validate_courier_can_receive(courier_profile)
        return CourierService._transition_locked(delivery, CourierDeliveryStatus.ASSIGNED, courier_profile.user, courier_profile=courier_profile)

    @staticmethod
    @transaction.atomic
    def update_status(delivery, courier_profile, next_status):
        delivery = CourierDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.courier_id != courier_profile.id:
            raise ValidationError('This delivery is not assigned to your courier profile.')
        return CourierService._transition_locked(delivery, next_status, courier_profile.user)

    @staticmethod
    def _transition_locked(delivery, next_status, actor_user, courier_profile=None):
        if delivery.is_terminal:
            raise ValidationError('Terminal deliveries cannot be updated.')
        allowed = ALLOWED_TRANSITIONS.get(delivery.status, set())
        if next_status not in allowed:
            raise ValidationError(f'Cannot move delivery from {delivery.status} to {next_status}.')

        delivery.status = next_status
        update_fields = ['status', 'updated_at']
        timestamp_field = STATUS_TIMESTAMPS.get(next_status)
        if timestamp_field:
            setattr(delivery, timestamp_field, timezone.now())
            update_fields.append(timestamp_field)
        if courier_profile is not None:
            delivery.courier = courier_profile
            update_fields.append('courier')
        if next_status == CourierDeliveryStatus.DELIVERED:
            delivery.final_fare = delivery.final_fare or delivery.estimated_fare
            update_fields.append('final_fare')
        delivery.save(update_fields=update_fields)
        CourierService._notify_status(delivery, actor_user)
        CourierService.broadcast_status(delivery, actor_user=actor_user)
        return delivery

    @staticmethod
    @transaction.atomic
    def cancel_delivery(delivery, actor, actor_type, reason=''):
        delivery = CourierDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.is_terminal:
            raise ValidationError('Delivered or cancelled deliveries cannot be cancelled.')
        if actor_type == CourierCancellationActor.CUSTOMER and delivery.customer_id != actor.id:
            raise ValidationError('You can only cancel your own courier deliveries.')
        if actor_type == CourierCancellationActor.CUSTOMER and not delivery.can_customer_cancel:
            raise ValidationError('This delivery can no longer be cancelled by the customer.')
        delivery.status = CourierDeliveryStatus.CANCELLED
        delivery.cancelled_at = timezone.now()
        delivery.cancelled_by = actor_type
        delivery.cancellation_reason = reason or ''
        delivery.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
        CourierService._notify_status(delivery, actor)
        CourierService.broadcast_status(delivery, 'Courier delivery cancelled.', actor_user=actor)
        return delivery

    @staticmethod
    @transaction.atomic
    def update_payment_status(delivery, status, final_fare=None):
        delivery = CourierDelivery.objects.select_for_update().get(pk=delivery.pk)
        if status not in CourierPaymentStatus.values:
            raise ValidationError('Invalid payment status.')
        delivery.payment_status = status
        update_fields = ['payment_status', 'updated_at']
        if final_fare is not None:
            delivery.final_fare = final_fare
            update_fields.append('final_fare')
        delivery.save(update_fields=update_fields)
        safe_notify(
            NotificationTemplates.payment_status_updated,
            delivery.customer,
            ProviderServiceCategory.COURIER,
            status,
            delivery.id,
            amount=str(delivery.final_fare or delivery.estimated_fare),
            currency=delivery.currency,
        )
        return delivery

    @staticmethod
    @transaction.atomic
    def submit_review(delivery, customer, data):
        delivery = CourierDelivery.objects.select_related('courier').get(pk=delivery.pk)
        if delivery.customer_id != customer.id:
            raise ValidationError('You can only review your own courier delivery.')
        if delivery.status != CourierDeliveryStatus.DELIVERED:
            raise ValidationError('Only delivered courier services can be reviewed.')
        if not delivery.courier:
            raise ValidationError('Delivery has no assigned courier to review.')
        review = CourierReview.objects.create(delivery=delivery, customer=customer, courier=delivery.courier, **data)
        if review.tip_amount:
            delivery.tip_amount = review.tip_amount
            delivery.save(update_fields=['tip_amount', 'updated_at'])
        safe_notify(
            NotificationTemplates.review_received,
            delivery.courier.user,
            ProviderServiceCategory.COURIER,
            delivery.id,
            rating=review.rating,
        )
        return review

    @staticmethod
    @transaction.atomic
    def update_courier_location(delivery, courier_profile, latitude, longitude):
        delivery = CourierDelivery.objects.select_for_update().get(pk=delivery.pk)
        if delivery.courier_id != courier_profile.id:
            raise ValidationError('This delivery is not assigned to your courier profile.')
        if delivery.status not in (CourierDeliveryStatus.ASSIGNED, CourierDeliveryStatus.PICKUP_ARRIVED, CourierDeliveryStatus.IN_TRANSIT):
            raise ValidationError('Courier location can only be updated for active assigned deliveries.')
        delivery.mark_courier_location(latitude, longitude)
        CourierService.broadcast_location(delivery)
        return delivery

    @staticmethod
    def provider_stats(courier_profile):
        today = timezone.localdate()
        deliveries = CourierDelivery.objects.filter(courier=courier_profile)
        reviews = CourierReview.objects.filter(courier=courier_profile)
        return {
            'deliveries_today': deliveries.filter(created_at__date=today).count(),
            'completed_deliveries_today': deliveries.filter(status=CourierDeliveryStatus.DELIVERED, delivered_at__date=today).count(),
            'total_earnings': deliveries.filter(status=CourierDeliveryStatus.DELIVERED).aggregate(total=Sum('final_fare'))['total'] or Decimal('0.00'),
            'average_rating': reviews.aggregate(avg=Avg('rating'))['avg'],
            'total_reviews': reviews.count(),
        }

    @staticmethod
    def broadcast_status(delivery, message='', actor_user=None):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            courier_delivery_tracking_group_name(delivery.id),
            {
                'type': 'courier.status',
                'delivery_id': str(delivery.id),
                'status': delivery.status,
                'message': message,
                'actor_user_id': str(actor_user.id) if actor_user else None,
                'timestamp': timezone.now().isoformat(),
            },
        )
        return True

    @staticmethod
    def broadcast_location(delivery):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            courier_delivery_tracking_group_name(delivery.id),
            {
                'type': 'courier.location',
                'delivery_id': str(delivery.id),
                'latitude': str(delivery.courier_current_latitude),
                'longitude': str(delivery.courier_current_longitude),
                'courier_location_updated_at': delivery.courier_location_updated_at.isoformat() if delivery.courier_location_updated_at else None,
            },
        )
        return True

    @staticmethod
    def _notify_status(delivery, actor):
        safe_notify(
            NotificationTemplates.service_status_updated,
            delivery.customer,
            ProviderServiceCategory.COURIER,
            delivery.status,
            delivery.id,
            actor=actor,
        )
