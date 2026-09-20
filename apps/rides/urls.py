from django.urls import path

from .views import (
    CustomerRideCancelView,
    CustomerRideDetailView,
    CustomerRideListCreateView,
    CustomerRideReviewView,
    ProviderAvailableRideListView,
    ProviderRideAcceptView,
    ProviderRideArrivedView,
    ProviderRideCompleteView,
    ProviderRideHistoryView,
    ProviderRideLocationUpdateView,
    ProviderRideStartView,
    RideFareEstimateView,
    SuperAdminRideDetailView,
    SuperAdminRideListView,
    SuperAdminRidePaymentStatusView,
)

app_name = 'rides'

urlpatterns = [
    path('fare-estimate/', RideFareEstimateView.as_view(), name='fare-estimate'),
    path('my-rides/', CustomerRideListCreateView.as_view(), name='customer-rides'),
    path('my-rides/<int:pk>/', CustomerRideDetailView.as_view(), name='customer-ride-detail'),
    path('my-rides/<int:pk>/cancel/', CustomerRideCancelView.as_view(), name='customer-ride-cancel'),
    path('my-rides/<int:pk>/review/', CustomerRideReviewView.as_view(), name='customer-ride-review'),

    path('provider/available/', ProviderAvailableRideListView.as_view(), name='provider-available-rides'),
    path('provider/history/', ProviderRideHistoryView.as_view(), name='provider-ride-history'),
    path('provider/rides/<int:pk>/accept/', ProviderRideAcceptView.as_view(), name='provider-ride-accept'),
    path('provider/rides/<int:pk>/arrived/', ProviderRideArrivedView.as_view(), name='provider-ride-arrived'),
    path('provider/rides/<int:pk>/start/', ProviderRideStartView.as_view(), name='provider-ride-start'),
    path('provider/rides/<int:pk>/complete/', ProviderRideCompleteView.as_view(), name='provider-ride-complete'),
    path('provider/rides/<int:pk>/location/', ProviderRideLocationUpdateView.as_view(), name='provider-ride-location'),

    path('admin/rides/', SuperAdminRideListView.as_view(), name='admin-rides'),
    path('admin/rides/<int:pk>/', SuperAdminRideDetailView.as_view(), name='admin-ride-detail'),
    path('admin/rides/<int:pk>/payment-status/', SuperAdminRidePaymentStatusView.as_view(), name='admin-ride-payment-status'),
]
