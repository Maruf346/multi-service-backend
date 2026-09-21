import json
from decimal import Decimal
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import FoodOrderStatus


class FoodOrderTrackingConsumer(AsyncWebsocketConsumer):
    """Customer, restaurant, and assigned courier room for food order tracking."""

    async def connect(self):
        self.order_id = self.scope['url_route']['kwargs']['order_id']
        token = self._extract_token()
        self.user = await self.get_user_from_token(token)
        self.order_role = await self.get_order_role(self.user, self.order_id)

        if not self.order_role:
            await self.close(code=4003)
            return

        self.group_name = food_order_tracking_group_name(self.order_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'order_id': str(self.order_id),
            'role': self.order_role,
            'message': 'Connected to food order tracking.',
        }))

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Invalid JSON payload.'}))
            return

        action = data.get('action')
        if action == 'courier_location_update':
            await self.handle_courier_location_update(data)
        else:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Unsupported action.'}))

    async def handle_courier_location_update(self, data):
        if self.order_role != 'courier':
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Only the assigned courier can update courier location.'}))
            return

        try:
            latitude = Decimal(str(data.get('latitude')))
            longitude = Decimal(str(data.get('longitude')))
        except Exception:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'latitude and longitude are required decimal values.'}))
            return

        result = await self.update_courier_location(self.order_id, self.user.id, latitude, longitude)
        if not result['ok']:
            await self.send(text_data=json.dumps({'type': 'error', 'message': result['message']}))
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'food.location',
                'order_id': str(self.order_id),
                'latitude': str(latitude),
                'longitude': str(longitude),
                'courier_location_updated_at': result['updated_at'],
            },
        )

    async def food_location(self, event):
        await self.send(text_data=json.dumps({
            'type': 'courier_location',
            'order_id': event.get('order_id'),
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude'),
            'courier_location_updated_at': event.get('courier_location_updated_at'),
        }))

    async def food_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'food_order_status',
            'order_id': event.get('order_id'),
            'status': event.get('status'),
            'message': event.get('message', ''),
            'actor_user_id': event.get('actor_user_id'),
            'timestamp': event.get('timestamp'),
        }))

    def _extract_token(self):
        query = self.scope.get('query_string', b'').decode()
        return parse_qs(query).get('token', [''])[0]

    @database_sync_to_async
    def get_user_from_token(self, token):
        if not token:
            return AnonymousUser()
        try:
            from rest_framework_simplejwt.authentication import JWTAuthentication

            jwt_auth = JWTAuthentication()
            validated_token = jwt_auth.get_validated_token(token)
            return jwt_auth.get_user(validated_token)
        except Exception:
            return AnonymousUser()

    @database_sync_to_async
    def get_order_role(self, user, order_id):
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return None

        from .models import FoodOrder

        try:
            order = FoodOrder.objects.select_related('restaurant', 'restaurant__user', 'courier', 'courier__user').get(pk=order_id)
        except FoodOrder.DoesNotExist:
            return None

        if order.customer_id == user.id:
            return 'customer'
        if order.restaurant.user_id == user.id:
            return 'restaurant'
        if order.courier and order.courier.user_id == user.id:
            return 'courier'
        return None

    @database_sync_to_async
    def update_courier_location(self, order_id, user_id, latitude, longitude):
        from .models import FoodOrder

        try:
            order = FoodOrder.objects.select_related('courier', 'courier__user').get(pk=order_id)
        except FoodOrder.DoesNotExist:
            return {'ok': False, 'message': 'Order not found.'}

        if not order.courier or order.courier.user_id != user_id:
            return {'ok': False, 'message': 'This order is not assigned to your courier profile.'}
        if order.status not in (FoodOrderStatus.COURIER_ASSIGNED, FoodOrderStatus.IN_TRANSIT):
            return {'ok': False, 'message': 'Courier location can only be updated for active assigned deliveries.'}

        order.mark_courier_location(latitude, longitude)
        return {'ok': True, 'updated_at': order.courier_location_updated_at.isoformat()}


def food_order_tracking_group_name(order_id):
    return f'food_order_tracking_{order_id}'
