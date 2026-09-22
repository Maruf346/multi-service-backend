import json
from decimal import Decimal
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import CourierDeliveryStatus


class CourierDeliveryTrackingConsumer(AsyncWebsocketConsumer):
    """Customer and assigned courier room for courier delivery tracking."""

    async def connect(self):
        self.delivery_id = self.scope['url_route']['kwargs']['delivery_id']
        token = self._extract_token()
        self.user = await self.get_user_from_token(token)
        self.delivery_role = await self.get_delivery_role(self.user, self.delivery_id)

        if not self.delivery_role:
            await self.close(code=4003)
            return

        self.group_name = courier_delivery_tracking_group_name(self.delivery_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'delivery_id': str(self.delivery_id),
            'role': self.delivery_role,
            'message': 'Connected to courier delivery tracking.',
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
        if self.delivery_role != 'courier':
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Only the assigned courier can update courier location.'}))
            return

        try:
            latitude = Decimal(str(data.get('latitude')))
            longitude = Decimal(str(data.get('longitude')))
        except Exception:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'latitude and longitude are required decimal values.'}))
            return

        result = await self.update_courier_location(self.delivery_id, self.user.id, latitude, longitude)
        if not result['ok']:
            await self.send(text_data=json.dumps({'type': 'error', 'message': result['message']}))
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'courier.location',
                'delivery_id': str(self.delivery_id),
                'latitude': str(latitude),
                'longitude': str(longitude),
                'courier_location_updated_at': result['updated_at'],
            },
        )

    async def courier_location(self, event):
        await self.send(text_data=json.dumps({
            'type': 'courier_location',
            'delivery_id': event.get('delivery_id'),
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude'),
            'courier_location_updated_at': event.get('courier_location_updated_at'),
        }))

    async def courier_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'courier_delivery_status',
            'delivery_id': event.get('delivery_id'),
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
    def get_delivery_role(self, user, delivery_id):
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return None

        from .models import CourierDelivery

        try:
            delivery = CourierDelivery.objects.select_related('requested_courier', 'requested_courier__user', 'courier', 'courier__user').get(pk=delivery_id)
        except CourierDelivery.DoesNotExist:
            return None

        if delivery.customer_id == user.id:
            return 'customer'
        if delivery.requested_courier.user_id == user.id:
            return 'courier'
        if delivery.courier and delivery.courier.user_id == user.id:
            return 'courier'
        return None

    @database_sync_to_async
    def update_courier_location(self, delivery_id, user_id, latitude, longitude):
        from .models import CourierDelivery

        try:
            delivery = CourierDelivery.objects.select_related('courier', 'courier__user').get(pk=delivery_id)
        except CourierDelivery.DoesNotExist:
            return {'ok': False, 'message': 'Delivery not found.'}

        if not delivery.courier or delivery.courier.user_id != user_id:
            return {'ok': False, 'message': 'This delivery is not assigned to your courier profile.'}
        if delivery.status not in (CourierDeliveryStatus.ASSIGNED, CourierDeliveryStatus.PICKUP_ARRIVED, CourierDeliveryStatus.IN_TRANSIT):
            return {'ok': False, 'message': 'Courier location can only be updated for active assigned deliveries.'}

        delivery.mark_courier_location(latitude, longitude)
        return {'ok': True, 'updated_at': delivery.courier_location_updated_at.isoformat()}


def courier_delivery_tracking_group_name(delivery_id):
    return f'courier_delivery_tracking_{delivery_id}'
