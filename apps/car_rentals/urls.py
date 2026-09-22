from django.urls import path

from .views import (
    CarRentalQuoteView,
    CustomerCarRentalBookingCancelView,
    CustomerCarRentalBookingDetailView,
    CustomerCarRentalBookingListCreateView,
    CustomerCarRentalReviewView,
    CustomerRentalVehicleDetailView,
    CustomerRentalVehicleListView,
    ProviderRentalBookingCompleteView,
    ProviderRentalBookingConfirmView,
    ProviderRentalBookingDeclineView,
    ProviderRentalBookingDetailView,
    ProviderRentalBookingListView,
    ProviderRentalReviewListView,
    ProviderRentalStatsView,
    ProviderRentalVehicleDetailView,
    ProviderRentalVehicleListCreateView,
    ProviderRentalVehicleMediaCreateView,
    RentalProviderDetailView,
    RentalProviderListView,
    SuperAdminCarRentalBookingDetailView,
    SuperAdminCarRentalBookingListView,
    SuperAdminCarRentalPaymentStatusView,
)

app_name = 'car_rentals'

urlpatterns = [
    path('providers/', RentalProviderListView.as_view(), name='providers'),
    path('providers/<int:pk>/', RentalProviderDetailView.as_view(), name='provider-detail'),
    path('vehicles/', CustomerRentalVehicleListView.as_view(), name='vehicles'),
    path('vehicles/<int:pk>/', CustomerRentalVehicleDetailView.as_view(), name='vehicle-detail'),
    path('quote/', CarRentalQuoteView.as_view(), name='quote'),
    path('my-bookings/', CustomerCarRentalBookingListCreateView.as_view(), name='customer-bookings'),
    path('my-bookings/<int:pk>/', CustomerCarRentalBookingDetailView.as_view(), name='customer-booking-detail'),
    path('my-bookings/<int:pk>/cancel/', CustomerCarRentalBookingCancelView.as_view(), name='customer-booking-cancel'),
    path('my-bookings/<int:pk>/review/', CustomerCarRentalReviewView.as_view(), name='customer-booking-review'),

    path('provider/vehicles/', ProviderRentalVehicleListCreateView.as_view(), name='provider-vehicles'),
    path('provider/vehicles/<int:pk>/', ProviderRentalVehicleDetailView.as_view(), name='provider-vehicle-detail'),
    path('provider/vehicles/<int:pk>/media/', ProviderRentalVehicleMediaCreateView.as_view(), name='provider-vehicle-media'),
    path('provider/bookings/', ProviderRentalBookingListView.as_view(), name='provider-bookings'),
    path('provider/bookings/<int:pk>/', ProviderRentalBookingDetailView.as_view(), name='provider-booking-detail'),
    path('provider/bookings/<int:pk>/confirm/', ProviderRentalBookingConfirmView.as_view(), name='provider-booking-confirm'),
    path('provider/bookings/<int:pk>/decline/', ProviderRentalBookingDeclineView.as_view(), name='provider-booking-decline'),
    path('provider/bookings/<int:pk>/complete/', ProviderRentalBookingCompleteView.as_view(), name='provider-booking-complete'),
    path('provider/stats/', ProviderRentalStatsView.as_view(), name='provider-stats'),
    path('provider/reviews/', ProviderRentalReviewListView.as_view(), name='provider-reviews'),

    path('admin/bookings/', SuperAdminCarRentalBookingListView.as_view(), name='admin-bookings'),
    path('admin/bookings/<int:pk>/', SuperAdminCarRentalBookingDetailView.as_view(), name='admin-booking-detail'),
    path('admin/bookings/<int:pk>/payment-status/', SuperAdminCarRentalPaymentStatusView.as_view(), name='admin-booking-payment-status'),
]
