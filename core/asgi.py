import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.conf import settings


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

from apps.notifications.routing import websocket_urlpatterns as notification_websocket_urlpatterns
from apps.rides.routing import websocket_urlpatterns as ride_websocket_urlpatterns
from apps.food.routing import websocket_urlpatterns as food_websocket_urlpatterns
from apps.courier.routing import websocket_urlpatterns as courier_websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(notification_websocket_urlpatterns + ride_websocket_urlpatterns + food_websocket_urlpatterns + courier_websocket_urlpatterns)
    ),
})
