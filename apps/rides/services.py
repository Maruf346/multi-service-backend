from decimal import Decimal, ROUND_HALF_UP

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.providers.models import ProviderOnboardingStatus, ProviderServiceCategory, RideProviderProfile
from .consumers import ride_tracking_group_name
from .models import RideCancellationActor, RidePaymentStatus, RideRequest, RideReview, RideStatus

BASE_FARE = Decimal('8.00')
PER_KM_RATE = Decimal('2.75')
PER_MINUTE_RATE = Decimal('0.65')
PASSENGER_SURCHARGE = Decimal('3.00')
MINIMUM_FARE = Decimal('12.00')


class RideService:
    @staticmethod
    def estimate_fare(distance_km=None, estimated_duration_minutes=None, passenger_count=1):
        distance = Decimal(str(distance_km or '0'))
        duration = Decimal(str(estimated_duration_minutes or '0'))
        passengers = max(int(passenger_count or 1), 1)
        passenger_extra = max(passengers - 1, 0) * PASSENGER_SURCHARGE
        fare = BASE_FARE + (distance * PER_KM_RATE) + (duration * PER_MINUTE_RATE) + passenger_extra
        fare = max(fare, MINIMUM_FARE)
        return fare.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @staticmethod
    @transaction.atomic
    def create_ride(customer, data):
        fare = RideService.estimate_fare(
            distance_km=data.get('distance_km'),
            estimated_duration_minutes=data.get('estimated_duration_minutes'),
            passenger_count=data.get('requested_passenger_count') or 1,
        )
        ride = RideRequest.objects.create(
            customer=customer,
            status=RideStatus.MATCHING,
            estimated_fare=fare,
            **data,
        )
        for driver in RideService.eligible_drivers(ride):
            safe_notify(
                NotificationTemplates.service_request_created,
                provider_user=driver.user,
                service_category=ProviderServiceCategory.RIDES,
                reference_id=ride.id,
                customer_user=customer,
            )
        return ride

    @staticmethod
    def eligible_drivers(ride=None):
        queryset = RideProviderProfile.objects.select_related('user').filter(
            onboarding_status=ProviderOnboardingStatus.COMPLETED,
            is_active=True,
            online_accepting_requests=True,
        )
        if ride:
            if ride.requested_vehicle_category:
                queryset = queryset.filter(vehicle_category=ride.requested_vehicle_category)
            queryset = queryset.filter(seat_capacity__gte=ride.requested_passenger_count)
        return queryset

    @staticmethod
    @transaction.atomic
    def accept_ride(ride, driver_profile):
        ride = RideRequest.objects.select_for_update().get(pk=ride.pk)
        if ride.status != RideStatus.MATCHING or ride.driver_id is not None:
            raise ValidationError('This ride is no longer available for acceptance.')
        RideService.validate_driver_can_accept(driver_profile, ride)
        now = timezone.now()
        ride.driver = driver_profile
        ride.status = RideStatus.ACCEPTED
        ride.accepted_at = now
        ride.save(update_fields=['driver', 'status', 'accepted_at', 'updated_at'])
        RideService.broadcast_status(ride, 'Ride accepted.', actor_user=driver_profile.user)
        safe_notify(
            NotificationTemplates.service_status_updated,
            user=ride.customer,
            service_category=ProviderServiceCategory.RIDES,
            status_label=ride.status,
            reference_id=ride.id,
            actor=driver_profile.user,
        )
        return ride

    @staticmethod
    def validate_driver_can_accept(driver_profile, ride):
        if not driver_profile:
            raise ValidationError('Ride provider profile not found.')
        if driver_profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Provider onboarding must be completed before accepting rides.')
        if not driver_profile.is_active or not driver_profile.online_accepting_requests:
            raise ValidationError('Driver is not online and accepting ride requests.')
        if ride.requested_vehicle_category and driver_profile.vehicle_category != ride.requested_vehicle_category:
            raise ValidationError('Driver vehicle category does not match this ride request.')
        if driver_profile.seat_capacity is not None and driver_profile.seat_capacity < ride.requested_passenger_count:
            raise ValidationError('Driver vehicle does not have enough passenger seats.')

    @staticmethod
    @transaction.atomic
    def mark_arrived(ride, driver_profile):
        ride = RideService._lock_driver_ride(ride, driver_profile)
        if ride.status != RideStatus.ACCEPTED:
            raise ValidationError('Only accepted rides can be marked as arrived.')
        ride.status = RideStatus.ARRIVED
        ride.arrived_at = timezone.now()
        ride.save(update_fields=['status', 'arrived_at', 'updated_at'])
        RideService._notify_status(ride, driver_profile.user)
        RideService.broadcast_status(ride, actor_user=driver_profile.user)
        return ride

    @staticmethod
    @transaction.atomic
    def start_ride(ride, driver_profile):
        ride = RideService._lock_driver_ride(ride, driver_profile)
        if ride.status not in (RideStatus.ACCEPTED, RideStatus.ARRIVED):
            raise ValidationError('Only accepted or arrived rides can be started.')
        ride.status = RideStatus.IN_PROGRESS
        ride.started_at = timezone.now()
        ride.save(update_fields=['status', 'started_at', 'updated_at'])
        RideService._notify_status(ride, driver_profile.user)
        RideService.broadcast_status(ride, actor_user=driver_profile.user)
        return ride

    @staticmethod
    @transaction.atomic
    def complete_ride(ride, driver_profile):
        ride = RideService._lock_driver_ride(ride, driver_profile)
        if ride.status != RideStatus.IN_PROGRESS:
            raise ValidationError('Only in-progress rides can be completed.')
        ride.status = RideStatus.COMPLETED
        ride.completed_at = timezone.now()
        ride.final_fare = ride.final_fare or ride.estimated_fare
        ride.save(update_fields=['status', 'completed_at', 'final_fare', 'updated_at'])
        RideService._notify_status(ride, driver_profile.user)
        RideService.broadcast_status(ride, actor_user=driver_profile.user)
        return ride

    @staticmethod
    @transaction.atomic
    def cancel_ride(ride, actor, actor_type, reason=''):
        ride = RideRequest.objects.select_for_update().get(pk=ride.pk)
        if ride.status in (RideStatus.COMPLETED, RideStatus.CANCELLED):
            raise ValidationError('Completed or cancelled rides cannot be cancelled.')
        if actor_type == RideCancellationActor.CUSTOMER and ride.customer_id != actor.id:
            raise ValidationError('You can only cancel your own rides.')
        if actor_type == RideCancellationActor.CUSTOMER and not ride.can_customer_cancel:
            raise ValidationError('This ride can no longer be cancelled by the customer.')
        ride.status = RideStatus.CANCELLED
        ride.cancelled_at = timezone.now()
        ride.cancelled_by = actor_type
        ride.cancellation_reason = reason or ''
        ride.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
        RideService.broadcast_status(ride, 'Ride cancelled.', actor_user=actor)
        if ride.driver:
            safe_notify(
                NotificationTemplates.service_status_updated,
                user=ride.driver.user,
                service_category=ProviderServiceCategory.RIDES,
                status_label=ride.status,
                reference_id=ride.id,
                actor=actor,
            )
        safe_notify(
            NotificationTemplates.service_status_updated,
            user=ride.customer,
            service_category=ProviderServiceCategory.RIDES,
            status_label=ride.status,
            reference_id=ride.id,
            actor=actor,
        )
        return ride

    @staticmethod
    @transaction.atomic
    def submit_review(ride, customer, data):
        ride = RideRequest.objects.select_related('driver').get(pk=ride.pk)
        if ride.customer_id != customer.id:
            raise ValidationError('You can only review your own ride.')
        if ride.status != RideStatus.COMPLETED:
            raise ValidationError('Only completed rides can be reviewed.')
        if not ride.driver:
            raise ValidationError('Ride has no assigned driver to review.')
        review = RideReview.objects.create(
            ride=ride,
            customer=customer,
            driver=ride.driver,
            **data,
        )
        if review.tip_amount:
            ride.tip_amount = review.tip_amount
            ride.save(update_fields=['tip_amount', 'updated_at'])
        safe_notify(
            NotificationTemplates.review_received,
            provider_user=ride.driver.user,
            service_category=ProviderServiceCategory.RIDES,
            reference_id=ride.id,
            rating=review.rating,
        )
        return review

    @staticmethod
    @transaction.atomic
    def update_payment_status(ride, status, final_fare=None):
        ride = RideRequest.objects.select_for_update().get(pk=ride.pk)
        if status not in RidePaymentStatus.values:
            raise ValidationError('Invalid payment status.')
        ride.payment_status = status
        update_fields = ['payment_status', 'updated_at']
        if final_fare is not None:
            ride.final_fare = final_fare
            update_fields.append('final_fare')
        ride.save(update_fields=update_fields)
        safe_notify(
            NotificationTemplates.payment_status_updated,
            user=ride.customer,
            service_category=ProviderServiceCategory.RIDES,
            status_label=status,
            reference_id=ride.id,
            amount=str(ride.final_fare or ride.estimated_fare),
            currency=ride.currency,
        )
        return ride


    @staticmethod
    def update_driver_location(ride, driver_profile, latitude, longitude):
        ride = RideService._lock_driver_ride(ride, driver_profile)
        if ride.status not in (RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS):
            raise ValidationError('Driver location can only be updated for active assigned rides.')
        ride.mark_driver_location(latitude, longitude)
        RideService.broadcast_location(ride)
        return ride

    @staticmethod
    def broadcast_status(ride, message='', actor_user=None):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            ride_tracking_group_name(ride.id),
            {
                'type': 'ride.status',
                'ride_id': str(ride.id),
                'status': ride.status,
                'message': message,
                'actor_user_id': str(actor_user.id) if actor_user else None,
                'timestamp': timezone.now().isoformat(),
            },
        )
        return True

    @staticmethod
    def broadcast_location(ride):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            ride_tracking_group_name(ride.id),
            {
                'type': 'ride.location',
                'ride_id': str(ride.id),
                'latitude': str(ride.driver_current_latitude),
                'longitude': str(ride.driver_current_longitude),
                'driver_location_updated_at': ride.driver_location_updated_at.isoformat() if ride.driver_location_updated_at else None,
            },
        )
        return True

    @staticmethod
    def _lock_driver_ride(ride, driver_profile):
        ride = RideRequest.objects.select_for_update().get(pk=ride.pk)
        if ride.driver_id != driver_profile.id:
            raise ValidationError('This ride is not assigned to your driver profile.')
        return ride

    @staticmethod
    def _notify_status(ride, actor):
        safe_notify(
            NotificationTemplates.service_status_updated,
            user=ride.customer,
            service_category=ProviderServiceCategory.RIDES,
            status_label=ride.status,
            reference_id=ride.id,
            actor=actor,
        )
