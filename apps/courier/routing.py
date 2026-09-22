from django.urls import path

from .consumers import CourierDeliveryTrackingConsumer


websocket_urlpatterns = [
    path('ws/courier/deliveries/<int:delivery_id>/tracking/', CourierDeliveryTrackingConsumer.as_asgi()),
]
