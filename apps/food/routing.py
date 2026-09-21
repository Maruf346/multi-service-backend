from django.urls import path

from .consumers import FoodOrderTrackingConsumer


websocket_urlpatterns = [
    path('ws/food/orders/<int:order_id>/tracking/', FoodOrderTrackingConsumer.as_asgi()),
]
