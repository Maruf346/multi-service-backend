from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.providers.models import ProviderOnboardingStatus, ProviderServiceCategory
from .models import (
    CarRentalBooking,
    CarRentalBookingStatus,
    CarRentalCancellationActor,
    CarRentalPaymentStatus,
    CarRentalReview,
)

VAT_RATE = Decimal('0.12')


class CarRentalService:
    @staticmethod
    def rental_days(start_date, end_date):
        days = (end_date - start_date).days + 1
        if days < 1:
            raise ValidationError({'end_date': 'End date must be on or after start date.'})
        return days

    @staticmethod
    def calculate_amounts(vehicle, start_date, end_date):
        rental_days = CarRentalService.rental_days(start_date, end_date)
        if rental_days < vehicle.minimum_rental_period_days:
            raise ValidationError({'rental_days': f'Minimum rental period is {vehicle.minimum_rental_period_days} day(s).'})
        rental_subtotal = (vehicle.daily_rate * rental_days).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        vat_amount = (rental_subtotal * VAT_RATE).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_amount = rental_subtotal + vat_amount + vehicle.security_escrow_deposit
        return {
            'rental_days': rental_days,
            'daily_rate': vehicle.daily_rate,
            'rental_subtotal': rental_subtotal,
            'vat_amount': vat_amount,
            'security_escrow_deposit': vehicle.security_escrow_deposit,
            'pre_auth_amount': vehicle.pre_auth_amount,
            'total_amount': total_amount,
            'currency': vehicle.currency,
        }

    @staticmethod
    def validate_provider_ready(provider):
        if provider.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Rental provider onboarding must be completed before receiving bookings.')
        if not provider.is_active:
            raise ValidationError('Rental provider is not active.')

    @staticmethod
    def validate_vehicle_available(vehicle, start_date, end_date, exclude_booking_id=None):
        if not vehicle.available:
            raise ValidationError('Vehicle is not currently available.')
        overlap = CarRentalBooking.objects.filter(
            vehicle=vehicle,
            status__in=[CarRentalBookingStatus.REQUESTED, CarRentalBookingStatus.CONFIRMED],
            start_date__lte=end_date,
            end_date__gte=start_date,
        )
        if exclude_booking_id:
            overlap = overlap.exclude(pk=exclude_booking_id)
        if overlap.exists():
            raise ValidationError('Vehicle already has a pending or confirmed booking for the selected dates.')

    @staticmethod
    @transaction.atomic
    def create_booking(customer, data):
        vehicle = data['vehicle']
        CarRentalService.validate_provider_ready(vehicle.provider)
        CarRentalService.validate_vehicle_available(vehicle, data['start_date'], data['end_date'])
        amounts = CarRentalService.calculate_amounts(vehicle, data['start_date'], data['end_date'])
        booking = CarRentalBooking.objects.create(
            customer=customer,
            provider=vehicle.provider,
            booking_number=CarRentalService.generate_booking_number(),
            **amounts,
            **data,
        )
        safe_notify(
            NotificationTemplates.service_request_created,
            booking.provider.user,
            ProviderServiceCategory.RENTALS,
            booking.id,
            customer_user=customer,
        )
        return booking

    @staticmethod
    def generate_booking_number():
        year_suffix = timezone.now().strftime('%y')
        prefix = f'BS-RENT-{year_suffix}'
        latest = CarRentalBooking.objects.filter(booking_number__startswith=prefix).order_by('-id').first()
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
        booking = CarRentalBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your rental provider profile.')
        if booking.status != CarRentalBookingStatus.REQUESTED:
            raise ValidationError('Only requested bookings can be confirmed.')
        CarRentalService.validate_vehicle_available(booking.vehicle, booking.start_date, booking.end_date, exclude_booking_id=booking.id)
        booking.status = CarRentalBookingStatus.CONFIRMED
        booking.confirmed_at = timezone.now()
        booking.decision_note = note or ''
        booking.save(update_fields=['status', 'confirmed_at', 'decision_note', 'updated_at'])
        CarRentalService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def decline_booking(booking, provider, note=''):
        booking = CarRentalBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your rental provider profile.')
        if booking.status != CarRentalBookingStatus.REQUESTED:
            raise ValidationError('Only requested bookings can be declined.')
        booking.status = CarRentalBookingStatus.DECLINED
        booking.declined_at = timezone.now()
        booking.decision_note = note or ''
        booking.save(update_fields=['status', 'declined_at', 'decision_note', 'updated_at'])
        CarRentalService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def complete_booking(booking, provider):
        booking = CarRentalBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.provider_id != provider.id:
            raise ValidationError('This booking does not belong to your rental provider profile.')
        if booking.status != CarRentalBookingStatus.CONFIRMED:
            raise ValidationError('Only confirmed bookings can be completed.')
        booking.status = CarRentalBookingStatus.COMPLETED
        booking.completed_at = timezone.now()
        booking.save(update_fields=['status', 'completed_at', 'updated_at'])
        CarRentalService._notify_status(booking, provider.user)
        return booking

    @staticmethod
    @transaction.atomic
    def cancel_booking(booking, actor, actor_type, reason=''):
        booking = CarRentalBooking.objects.select_for_update().get(pk=booking.pk)
        if booking.is_terminal:
            raise ValidationError('Terminal bookings cannot be cancelled.')
        if actor_type == CarRentalCancellationActor.CUSTOMER and booking.customer_id != actor.id:
            raise ValidationError('You can only cancel your own car rental bookings.')
        if actor_type == CarRentalCancellationActor.CUSTOMER and not booking.can_customer_cancel:
            raise ValidationError('This booking can no longer be cancelled by the customer.')
        booking.status = CarRentalBookingStatus.CANCELLED
        booking.cancelled_at = timezone.now()
        booking.cancelled_by = actor_type
        booking.cancellation_reason = reason or ''
        booking.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
        CarRentalService._notify_status(booking, actor)
        return booking

    @staticmethod
    @transaction.atomic
    def update_payment_status(booking, status, total_amount=None):
        booking = CarRentalBooking.objects.select_for_update().get(pk=booking.pk)
        if status not in CarRentalPaymentStatus.values:
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
            ProviderServiceCategory.RENTALS,
            status,
            booking.id,
            amount=str(booking.total_amount),
            currency=booking.currency,
        )
        return booking

    @staticmethod
    @transaction.atomic
    def submit_review(booking, customer, data):
        booking = CarRentalBooking.objects.select_related('vehicle', 'provider').get(pk=booking.pk)
        if booking.customer_id != customer.id:
            raise ValidationError('You can only review your own car rental booking.')
        if booking.status != CarRentalBookingStatus.COMPLETED:
            raise ValidationError('Only completed car rental bookings can be reviewed.')
        review = CarRentalReview.objects.create(
            booking=booking,
            customer=customer,
            provider=booking.provider,
            vehicle=booking.vehicle,
            **data,
        )
        safe_notify(
            NotificationTemplates.review_received,
            booking.provider.user,
            ProviderServiceCategory.RENTALS,
            booking.id,
            rating=review.rating,
        )
        return review

    @staticmethod
    def provider_stats(provider):
        bookings = CarRentalBooking.objects.filter(provider=provider)
        reviews = CarRentalReview.objects.filter(provider=provider)
        return {
            'total_vehicles': provider.rental_vehicles.count(),
            'available_vehicles': provider.rental_vehicles.filter(available=True).count(),
            'requested_bookings': bookings.filter(status=CarRentalBookingStatus.REQUESTED).count(),
            'confirmed_bookings': bookings.filter(status=CarRentalBookingStatus.CONFIRMED).count(),
            'completed_bookings': bookings.filter(status=CarRentalBookingStatus.COMPLETED).count(),
            'average_rating': reviews.aggregate(avg=Avg('rating'))['avg'],
            'total_reviews': reviews.count(),
        }

    @staticmethod
    def _notify_status(booking, actor):
        safe_notify(
            NotificationTemplates.service_status_updated,
            booking.customer,
            ProviderServiceCategory.RENTALS,
            booking.status,
            booking.id,
            actor=actor,
        )
