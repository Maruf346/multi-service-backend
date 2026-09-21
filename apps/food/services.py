from decimal import Decimal

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.providers.models import CourierProviderProfile, ProviderOnboardingStatus, ProviderServiceCategory
from .consumers import food_order_tracking_group_name
from .models import (
    FoodCancellationActor,
    FoodItem,
    FoodItemReview,
    FoodOrder,
    FoodOrderItem,
    FoodOrderStatus,
    FoodPaymentMethod,
    FoodPaymentStatus,
)

DEFAULT_DELIVERY_FEE = Decimal('4.00')
DEFAULT_SERVICE_FEE = Decimal('1.50')

STATUS_TIMESTAMPS = {
    FoodOrderStatus.CONFIRMED: 'confirmed_at',
    FoodOrderStatus.IN_PREP: 'in_prep_at',
    FoodOrderStatus.KITCHEN_SEALED: 'kitchen_sealed_at',
    FoodOrderStatus.COURIER_ASSIGNED: 'courier_assigned_at',
    FoodOrderStatus.IN_TRANSIT: 'in_transit_at',
    FoodOrderStatus.HANDED_OVER: 'handed_over_at',
}

ALLOWED_PROVIDER_TRANSITIONS = {
    FoodOrderStatus.PLACED: {FoodOrderStatus.CONFIRMED, FoodOrderStatus.CANCELLED},
    FoodOrderStatus.CONFIRMED: {FoodOrderStatus.IN_PREP, FoodOrderStatus.CANCELLED},
    FoodOrderStatus.IN_PREP: {FoodOrderStatus.KITCHEN_SEALED, FoodOrderStatus.CANCELLED},
    FoodOrderStatus.KITCHEN_SEALED: {FoodOrderStatus.COURIER_ASSIGNED, FoodOrderStatus.CANCELLED},
    FoodOrderStatus.COURIER_ASSIGNED: {FoodOrderStatus.IN_TRANSIT, FoodOrderStatus.CANCELLED},
    FoodOrderStatus.IN_TRANSIT: {FoodOrderStatus.HANDED_OVER, FoodOrderStatus.CANCELLED},
}


class FoodService:
    @staticmethod
    def validate_json_string_list(value, field_name):
        if not isinstance(value, list):
            raise ValidationError({field_name: 'This field must be a list of selected labels.'})
        if any(not isinstance(item, str) for item in value):
            raise ValidationError({field_name: 'Each selected label must be a string.'})
        return value

    @staticmethod
    def ensure_restaurant_can_receive_orders(restaurant):
        if restaurant.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Restaurant onboarding must be completed before receiving orders.')
        if not restaurant.is_active or not restaurant.accepting_orders:
            raise ValidationError('Restaurant is not accepting orders right now.')

    @staticmethod
    @transaction.atomic
    def create_order(customer, data):
        restaurant = data['restaurant']
        FoodService.ensure_restaurant_can_receive_orders(restaurant)

        item_inputs = data.pop('items')
        food_item_ids = [item['food_item_id'] for item in item_inputs]
        food_items = {
            item.id: item
            for item in FoodItem.objects.select_related('category', 'restaurant').filter(
                id__in=food_item_ids,
                restaurant=restaurant,
                is_active=True,
                available_today=True,
            )
        }
        missing_ids = sorted(set(food_item_ids) - set(food_items))
        if missing_ids:
            raise ValidationError({'items': f'Food items are unavailable or do not belong to this restaurant: {missing_ids}'})

        subtotal = Decimal('0.00')
        order_lines = []
        for item_input in item_inputs:
            food_item = food_items[item_input['food_item_id']]
            quantity = item_input['quantity']
            line_total = food_item.price * quantity
            subtotal += line_total
            order_lines.append((food_item, quantity, line_total, item_input.get('notes', '')))

        delivery_fee = data.pop('delivery_fee', DEFAULT_DELIVERY_FEE)
        service_fee = data.pop('service_fee', DEFAULT_SERVICE_FEE)
        tip_amount = data.pop('tip_amount', Decimal('0.00'))
        total_amount = subtotal + delivery_fee + service_fee
        payment_method = data.get('payment_method', FoodPaymentMethod.CASH_ON_DELIVERY)
        payment_status = FoodPaymentStatus.CASH_DUE if payment_method == FoodPaymentMethod.CASH_ON_DELIVERY else FoodPaymentStatus.PENDING

        order = FoodOrder.objects.create(
            customer=customer,
            subtotal=subtotal,
            delivery_fee=delivery_fee,
            service_fee=service_fee,
            total_amount=total_amount,
            tip_amount=tip_amount,
            payment_status=payment_status,
            **data,
        )
        FoodOrderItem.objects.bulk_create([
            FoodOrderItem(
                order=order,
                food_item=food_item,
                item_name=food_item.name,
                category_name=food_item.category.name,
                quantity=quantity,
                unit_price=food_item.price,
                line_total=line_total,
                currency=food_item.currency,
                notes=notes,
            )
            for food_item, quantity, line_total, notes in order_lines
        ])
        safe_notify(
            NotificationTemplates.service_request_created,
            order.restaurant.user,
            ProviderServiceCategory.RESTAURANTS,
            order.id,
            customer_user=customer,
        )
        FoodService.broadcast_status(order, 'Order placed.', actor_user=customer)
        return order

    @staticmethod
    @transaction.atomic
    def update_status(order, restaurant, next_status, actor_user=None, courier_profile=None):
        order = FoodOrder.objects.select_for_update().get(pk=order.pk)
        if order.restaurant_id != restaurant.id:
            raise ValidationError('This order does not belong to your restaurant.')
        if order.is_terminal:
            raise ValidationError('Terminal orders cannot be updated.')
        allowed = ALLOWED_PROVIDER_TRANSITIONS.get(order.status, set())
        if next_status not in allowed:
            raise ValidationError(f'Cannot move order from {order.status} to {next_status}.')

        update_fields = ['status', 'updated_at']
        order.status = next_status
        timestamp_field = STATUS_TIMESTAMPS.get(next_status)
        if timestamp_field:
            setattr(order, timestamp_field, timezone.now())
            update_fields.append(timestamp_field)

        if courier_profile is not None:
            if courier_profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
                raise ValidationError('Courier onboarding must be completed before assignment.')
            order.courier = courier_profile
            update_fields.append('courier')

        order.save(update_fields=update_fields)
        FoodService._notify_status(order, actor_user or restaurant.user)
        FoodService.broadcast_status(order, actor_user=actor_user or restaurant.user)
        return order

    @staticmethod
    @transaction.atomic
    def cancel_order(order, actor, actor_type, reason=''):
        order = FoodOrder.objects.select_for_update().get(pk=order.pk)
        if order.is_terminal:
            raise ValidationError('Completed or cancelled orders cannot be cancelled.')
        if actor_type == FoodCancellationActor.CUSTOMER and order.customer_id != actor.id:
            raise ValidationError('You can only cancel your own food orders.')
        if actor_type == FoodCancellationActor.CUSTOMER and not order.can_customer_cancel:
            raise ValidationError('This order can no longer be cancelled by the customer.')
        order.status = FoodOrderStatus.CANCELLED
        order.cancelled_at = timezone.now()
        order.cancelled_by = actor_type
        order.cancellation_reason = reason or ''
        order.save(update_fields=['status', 'cancelled_at', 'cancelled_by', 'cancellation_reason', 'updated_at'])
        FoodService._notify_status(order, actor)
        FoodService.broadcast_status(order, 'Order cancelled.', actor_user=actor)
        return order

    @staticmethod
    @transaction.atomic
    def update_payment_status(order, status, total_amount=None):
        order = FoodOrder.objects.select_for_update().get(pk=order.pk)
        if status not in FoodPaymentStatus.values:
            raise ValidationError('Invalid payment status.')
        order.payment_status = status
        update_fields = ['payment_status', 'updated_at']
        if total_amount is not None:
            order.total_amount = total_amount
            update_fields.append('total_amount')
        order.save(update_fields=update_fields)
        safe_notify(
            NotificationTemplates.payment_status_updated,
            order.customer,
            ProviderServiceCategory.RESTAURANTS,
            status,
            order.id,
            amount=str(order.total_amount),
            currency=order.currency,
        )
        return order

    @staticmethod
    @transaction.atomic
    def submit_item_review(order_item, customer, data):
        order_item = FoodOrderItem.objects.select_related('order', 'food_item').get(pk=order_item.pk)
        if order_item.order.customer_id != customer.id:
            raise ValidationError('You can only review your own ordered food items.')
        if order_item.order.status != FoodOrderStatus.HANDED_OVER:
            raise ValidationError('Food items can only be reviewed after handover.')
        review = FoodItemReview.objects.create(
            order_item=order_item,
            customer=customer,
            restaurant=order_item.order.restaurant,
            food_item=order_item.food_item,
            **data,
        )
        if review.tip_amount:
            order = order_item.order
            order.tip_amount = order.tip_amount + review.tip_amount
            order.save(update_fields=['tip_amount', 'updated_at'])
        safe_notify(
            NotificationTemplates.review_received,
            order_item.order.restaurant.user,
            ProviderServiceCategory.RESTAURANTS,
            order_item.order.id,
            rating=review.rating,
        )
        return review

    @staticmethod
    @transaction.atomic
    def update_courier_location(order, courier_profile, latitude, longitude):
        order = FoodOrder.objects.select_for_update().get(pk=order.pk)
        if order.courier_id != courier_profile.id:
            raise ValidationError('This order is not assigned to your courier profile.')
        if order.status not in (FoodOrderStatus.COURIER_ASSIGNED, FoodOrderStatus.IN_TRANSIT):
            raise ValidationError('Courier location can only be updated for active assigned deliveries.')
        order.mark_courier_location(latitude, longitude)
        FoodService.broadcast_location(order)
        return order

    @staticmethod
    def broadcast_status(order, message='', actor_user=None):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            food_order_tracking_group_name(order.id),
            {
                'type': 'food.status',
                'order_id': str(order.id),
                'status': order.status,
                'message': message,
                'actor_user_id': str(actor_user.id) if actor_user else None,
                'timestamp': timezone.now().isoformat(),
            },
        )
        return True

    @staticmethod
    def broadcast_location(order):
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return False
        async_to_sync(channel_layer.group_send)(
            food_order_tracking_group_name(order.id),
            {
                'type': 'food.location',
                'order_id': str(order.id),
                'latitude': str(order.courier_current_latitude),
                'longitude': str(order.courier_current_longitude),
                'courier_location_updated_at': order.courier_location_updated_at.isoformat() if order.courier_location_updated_at else None,
            },
        )
        return True

    @staticmethod
    def _notify_status(order, actor):
        safe_notify(
            NotificationTemplates.service_status_updated,
            order.customer,
            ProviderServiceCategory.RESTAURANTS,
            order.status,
            order.id,
            actor=actor,
        )
