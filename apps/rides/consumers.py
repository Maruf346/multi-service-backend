import json
from decimal import Decimal
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

from .models import RideStatus


class RideTrackingConsumer(AsyncWebsocketConsumer):
    """Customer/driver websocket room for an accepted ride's live tracking."""

    async def connect(self):
        self.ride_id = self.scope['url_route']['kwargs']['ride_id']
        token = self._extract_token()
        self.user = await self.get_user_from_token(token)
        self.ride_role = await self.get_ride_role(self.user, self.ride_id)

        if not self.ride_role:
            await self.close(code=4003)
            return

        self.group_name = ride_tracking_group_name(self.ride_id)
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'ride_id': str(self.ride_id),
            'role': self.ride_role,
            'message': 'Connected to ride tracking.',
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
        if action == 'driver_location_update':
            await self.handle_driver_location_update(data)
        else:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Unsupported action.'}))

    async def handle_driver_location_update(self, data):
        if self.ride_role != 'driver':
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Only the assigned driver can update driver location.'}))
            return

        try:
            latitude = Decimal(str(data.get('latitude')))
            longitude = Decimal(str(data.get('longitude')))
        except Exception:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'latitude and longitude are required decimal values.'}))
            return

        result = await self.update_driver_location(self.ride_id, self.user.id, latitude, longitude)
        if not result['ok']:
            await self.send(text_data=json.dumps({'type': 'error', 'message': result['message']}))
            return

        await self.channel_layer.group_send(
            self.group_name,
            {
                'type': 'ride.location',
                'ride_id': str(self.ride_id),
                'latitude': str(latitude),
                'longitude': str(longitude),
                'driver_location_updated_at': result['updated_at'],
            },
        )

    async def ride_location(self, event):
        await self.send(text_data=json.dumps({
            'type': 'driver_location',
            'ride_id': event.get('ride_id'),
            'latitude': event.get('latitude'),
            'longitude': event.get('longitude'),
            'driver_location_updated_at': event.get('driver_location_updated_at'),
        }))

    async def ride_status(self, event):
        await self.send(text_data=json.dumps({
            'type': 'ride_status',
            'ride_id': event.get('ride_id'),
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
    def get_ride_role(self, user, ride_id):
        if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
            return None

        from .models import RideRequest

        try:
            ride = RideRequest.objects.select_related('driver', 'driver__user').get(pk=ride_id)
        except RideRequest.DoesNotExist:
            return None

        if ride.customer_id == user.id:
            return 'customer'
        if ride.driver and ride.driver.user_id == user.id:
            return 'driver'
        return None

    @database_sync_to_async
    def update_driver_location(self, ride_id, user_id, latitude, longitude):
        from .models import RideRequest

        try:
            ride = RideRequest.objects.select_related('driver', 'driver__user').get(pk=ride_id)
        except RideRequest.DoesNotExist:
            return {'ok': False, 'message': 'Ride not found.'}

        if not ride.driver or ride.driver.user_id != user_id:
            return {'ok': False, 'message': 'This ride is not assigned to your driver profile.'}
        if ride.status not in (RideStatus.ACCEPTED, RideStatus.ARRIVED, RideStatus.IN_PROGRESS):
            return {'ok': False, 'message': 'Driver location can only be updated for active assigned rides.'}

        ride.mark_driver_location(latitude, longitude)
        return {'ok': True, 'updated_at': ride.driver_location_updated_at.isoformat()}


def ride_tracking_group_name(ride_id):
    return f'ride_tracking_{ride_id}'
