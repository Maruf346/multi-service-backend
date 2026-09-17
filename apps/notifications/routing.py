from django.urls import path

from .consumers import NotificationConsumer


websocket_urlpatterns = [
    path('ws/superadmin/notifications/', NotificationConsumer.as_asgi()),
]
