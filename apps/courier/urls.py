from django.urls import path

from .views import (
    CourierFareEstimateView,
    CourierProviderDetailView,
    CourierProviderListView,
    CustomerCourierDeliveryCancelView,
    CustomerCourierDeliveryDetailView,
    CustomerCourierDeliveryListCreateView,
    CustomerCourierDeliveryReviewView,
    ProviderCourierAcceptView,
    ProviderCourierDeliveryDetailView,
    ProviderCourierHistoryView,
    ProviderCourierLocationView,
    ProviderCourierRequestListView,
    ProviderCourierReviewListView,
    ProviderCourierStatsView,
    ProviderCourierStatusView,
    SuperAdminCourierDeliveryDetailView,
    SuperAdminCourierDeliveryListView,
    SuperAdminCourierPaymentStatusView,
)

app_name = 'courier'

urlpatterns = [
    path('providers/', CourierProviderListView.as_view(), name='providers'),
    path('providers/<int:pk>/', CourierProviderDetailView.as_view(), name='provider-detail'),
    path('fare-estimate/', CourierFareEstimateView.as_view(), name='fare-estimate'),
    path('my-deliveries/', CustomerCourierDeliveryListCreateView.as_view(), name='customer-deliveries'),
    path('my-deliveries/<int:pk>/', CustomerCourierDeliveryDetailView.as_view(), name='customer-delivery-detail'),
    path('my-deliveries/<int:pk>/cancel/', CustomerCourierDeliveryCancelView.as_view(), name='customer-delivery-cancel'),
    path('my-deliveries/<int:pk>/review/', CustomerCourierDeliveryReviewView.as_view(), name='customer-delivery-review'),

    path('provider/requests/', ProviderCourierRequestListView.as_view(), name='provider-requests'),
    path('provider/history/', ProviderCourierHistoryView.as_view(), name='provider-history'),
    path('provider/stats/', ProviderCourierStatsView.as_view(), name='provider-stats'),
    path('provider/reviews/', ProviderCourierReviewListView.as_view(), name='provider-reviews'),
    path('provider/deliveries/<int:pk>/', ProviderCourierDeliveryDetailView.as_view(), name='provider-delivery-detail'),
    path('provider/deliveries/<int:pk>/accept/', ProviderCourierAcceptView.as_view(), name='provider-delivery-accept'),
    path('provider/deliveries/<int:pk>/status/', ProviderCourierStatusView.as_view(), name='provider-delivery-status'),
    path('provider/deliveries/<int:pk>/location/', ProviderCourierLocationView.as_view(), name='provider-delivery-location'),

    path('admin/deliveries/', SuperAdminCourierDeliveryListView.as_view(), name='admin-deliveries'),
    path('admin/deliveries/<int:pk>/', SuperAdminCourierDeliveryDetailView.as_view(), name='admin-delivery-detail'),
    path('admin/deliveries/<int:pk>/payment-status/', SuperAdminCourierPaymentStatusView.as_view(), name='admin-delivery-payment-status'),
]
