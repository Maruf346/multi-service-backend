from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg
from django.utils import timezone

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.providers.models import ProviderOnboardingStatus, ProviderServiceCategory
from .models import PropertyAvailability, RoomBooking, RoomBookingStatus, RoomCancellationActor, RoomPaymentStatus, RoomReview


class RoomService:
    @staticmethod
    def stay_nights(check_in_date, check_out_date):
        nights = (check_out_date - check_in_date).days
        if nights < 1:
            raise ValidationError({'check_out_date': 'Check-out date must be after check-in date.'})
        return nights

    @staticmethod
    def quote(listing, check_in_date, check_out_date):
        nights = RoomService.stay_nights(check_in_date, check_out_date)
        if nights < listing.minimum_stay_nights:
            raise ValidationError({'nights': f'Minimum stay is {listing.minimum_stay_nights} night(s).'})
        nightly_rate = listing.nightly_base_rate
        stay_subtotal = nightly_rate * nights
        total_amount = stay_subtotal + listing.cleaning_fee + listing.security_damage_deposit
        return {
            'nights': nights,
            'nightly_rate': nightly_rate,
            'stay_subtotal': stay_subtotal,
            'cleaning_fee': listing.cleaning_fee,
            'security_damage_deposit': listing.security_damage_deposit,
            'total_amount': total_amount,
            'currency': listing.currency,
        }

    @staticmethod
    def validate_provider_ready(provider):
        if provider.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Property provider onboarding must be completed before receiving bookings.')
        if not provider.is_active:
            raise ValidationError('Property provider is not active.')

    @staticmethod
    def validate_listing_available(listing, check_in_date, check_out_date, number_of_persons=None, exclude_booking_id=None):
        if not listing.is_active:
            raise ValidationError('Property listing is not active.')
        if number_of_persons and number_of_persons > listing.max_guests:
            raise ValidationError({'number_of_persons': 'Number of persons exceeds listing max guests.'})
        nights = RoomService.stay_nights(check_in_date, check_out_date)
        blocked = PropertyAvailability.objects.filter(
            listing=listing,
            date__gte=check_in_date,
            date__lt=check_out_date,
            is_available=False,
        )
        if blocked.exists():
            raise ValidationError('Listing is unavailable for one or more selected dates.')
        overlap = RoomBooking.objects.filter(
            listing=listing,
            status__in=[RoomBookingStatus.REQUESTED, RoomBookingStatus.CONFIRMED],
            check_in_date__lt=check_out_date,
            check_out_date__gt=check_in_date,
        )
        if exclude_booking_id:
            overlap = overlap.exclude(pk=exclude_booking_id)
        if overlap.exists():
            raise ValidationError('Listing already has a pending or confirmed booking for the selected dates.')
        return nights

    @staticmethod
    @transaction.atomic
    def create_booking(customer, data):
        listing = data['listing']
        RoomService.validate_provider_ready(listing.provider)
        RoomService.validate_listing_available(listing, data['check_in_date'], data['check_out_date'], data.get('number_of_persons'))
        amounts = RoomService.quote(listing, data['check_in_date'], data['check_out_date'])
        booking = RoomBooking.objects.create(
            customer=customer,
            provider=listing.provider,
            booking_number=RoomService.generate_booking_number(),
            **amounts,
            **data,
        )
        safe_notify(
            NotificationTemplates.service_request_created,
            booking.provider.user,
            ProviderServiceCategory.PROPERTIES,
            booking.id,
            customer_user=customer,
        )
        return booking

    @staticmethod
    def generate_booking_number():
        year_suffix = timezone.now().strftime('%y')
        prefix = f'BS-ROOM-{year_suffix}'
        latest = RoomBooking.objects.filter(booking_number__startswith=prefix).order_by('-id').first()
        next_number = 1
        if latest and latest.booking_number:
            try:
                next_number = int(latest.booking_number.rsplit('-', 1)[-1]) + 1
            except ValueError:
                next_number = latest.id + 1
        return f'{prefix}-{next_number:04d}'

    @staticmethod
    @transaction.atomic
    def confirm_booking(booking, provider, note=''):
        booking = RoomBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your property provider profile.')
        if booking.status != RoomBookingStatus.REQUESTED:
            raise ValidationError('Only requested bookings can be confirmed.')
        RoomService.validate_listing_available(booking.listing, booking.check_in_date, booking.check_out_date, booking.number_of_persons, exclude_booking_id=booking.id)
        booking.status = RoomBookingStatus.CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.decision_note = note or ''
        booking.save(update_fields=['status', 'confirmed_at', 'decision_note', 'updated_at'])
        RoomService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def decline_booking(booking, provider, note=''):
        booking = RoomBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your property provider profile.')
        if booking.status != RoomBookingStatus.REQUESTED:
            raise ValidationError('Only requested bookings can be declined.')
        booking.status = RoomBookingStatus.DECLINED
        booking.declined_at = timezone.now()
        booking.decision_note = note or ''
        booking.save(update_fields=['status', 'declined_at', 'decision_note', 'updated_at'])
        RoomService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def complete_booking(booking, provider):
        booking = RoomBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your property provider profile.')
        if booking.status != RoomBookingStatus.CONFIRMED:
            raise ValidationError('Only confirmed bookings can be completed.')
        booking.status = RoomBookingStatus.COMPLETED
        booking.completed_at = timezone.now()
        booking.save(update_fields=['status', 'completed_at', 'updated_at'])
        RoomService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking, actor, actor_type, reason=''):
        booking = RoomBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.is_terminal:
            raise ValidationError('Terminal bookings cannot be cancelled.')
        if actor_type == RoomCancellationActor.CUSTOMER and booking.customer_id != actor.id:
            raise ValidationError('You can only cancel your own room bookings.')
        if actor_type == RoomCancellationActor.CUSTOMER and not booking.can_customer_cancel:
            raise ValidationError('This booking can no longer be cancelled by the customer.')
        booking.status = RoomBookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = actor_type
        booking.cancellation_reason = reason or ''
        booking.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
        RoomService._notify_status(booking, actor)
        return booking

    @staticmethod
    @transaction.atomic
    def update_payment_status(booking, status, total_amount=None):
        booking = RoomBooking.objects.select_for_update().get(pk=booking.pk)
        if status not in RoomPaymentStatus.values:
            raise ValidationError('Invalid payment status.')
        booking.payment_status = status
        update_fields = ['payment_status', 'updated_at']
        if total_amount is not None:
            booking.total_amount = total_amount
            update_fields.append('total_amount')
        booking.save(update_fields=update_fields)
        safe_notify(
            NotificationTemplates.payment_status_updated,
            booking.customer,
            ProviderServiceCategory.PROPERTIES,
            status,
            booking.id,
            amount=str(booking.total_amount),
            currency=booking.currency,
        )
        return booking

    @staticmethod
    @transaction.atomic
    def submit_review(booking, customer, data):
        booking = RoomBooking.objects.select_related('listing', 'provider').get(pk=booking.pk)
        if booking.customer_id != customer.id:
            raise ValidationError('You can only review your own room booking.')
        if booking.status != RoomBookingStatus.COMPLETED:
            raise ValidationError('Only completed room bookings can be reviewed.')
        review = RoomReview.objects.create(
            booking=booking,
            customer=customer,
            provider=booking.provider,
            listing=booking.listing,
            **data,
        )
        safe_notify(
            NotificationTemplates.review_received,
            booking.provider.user,
            ProviderServiceCategory.PROPERTIES,
            booking.id,
            rating=review.rating,
        )
        return review

    @staticmethod
    def provider_stats(provider):
        bookings = RoomBooking.objects.filter(provider=provider)
        reviews = RoomReview.objects.filter(provider=provider)
        return {
            'total_listings': provider.property_listings.count(),
            'active_listings': provider.property_listings.filter(is_active=True).count(),
            'requested_bookings': bookings.filter(status=RoomBookingStatus.REQUESTED).count(),
            'confirmed_bookings': bookings.filter(status=RoomBookingStatus.CONFIRMED).count(),
            'completed_bookings': bookings.filter(status=RoomBookingStatus.COMPLETED).count(),
            'average_rating': reviews.aggregate(avg=Avg('rating'))['avg'],
            'total_reviews': reviews.count(),
        }

    @staticmethod
    def _notify_status(booking, actor):
        safe_notify(
            NotificationTemplates.service_status_updated,
            booking.customer,
            ProviderServiceCategory.PROPERTIES,
            booking.status,
            booking.id,
            actor=actor,
        )
