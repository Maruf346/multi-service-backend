from django.urls import path

from .views import *

app_name = 'room_services'

urlpatterns = [
    path('providers/', PropertyProviderListView.as_view(), name='providers'),
    path('providers/<int:pk>/', PropertyProviderDetailView.as_view(), name='provider-detail'),
    path('listings/', CustomerPropertyListingListView.as_view(), name='listings'),
    path('listings/<int:pk>/', CustomerPropertyListingDetailView.as_view(), name='listing-detail'),
    path('quote/', RoomQuoteView.as_view(), name='quote'),
    path('my-bookings/', CustomerRoomBookingListCreateView.as_view(), name='customer-bookings'),
    path('my-bookings/<int:pk>/', CustomerRoomBookingDetailView.as_view(), name='customer-booking-detail'),
    path('my-bookings/<int:pk>/cancel/', CustomerRoomBookingCancelView.as_view(), name='customer-booking-cancel'),
    path('my-bookings/<int:pk>/review/', CustomerRoomReviewView.as_view(), name='customer-booking-review'),

    path('provider/listings/', ProviderListingListCreateView.as_view(), name='provider-listings'),
    path('provider/listings/<int:pk>/', ProviderListingDetailView.as_view(), name='provider-listing-detail'),
    path('provider/listings/<int:pk>/photos/', ProviderListingPhotoCreateView.as_view(), name='provider-listing-photo'),
    path('provider/listings/<int:listing_pk>/availability/', ProviderAvailabilityListCreateView.as_view(), name='provider-listing-availability'),
    path('provider/bookings/', ProviderBookingListView.as_view(), name='provider-bookings'),
    path('provider/bookings/<int:pk>/', ProviderBookingDetailView.as_view(), name='provider-booking-detail'),
    path('provider/bookings/<int:pk>/confirm/', ProviderBookingConfirmView.as_view(), name='provider-booking-confirm'),
    path('provider/bookings/<int:pk>/decline/', ProviderBookingDeclineView.as_view(), name='provider-booking-decline'),
    path('provider/bookings/<int:pk>/complete/', ProviderBookingCompleteView.as_view(), name='provider-booking-complete'),
    path('provider/stats/', ProviderRoomStatsView.as_view(), name='provider-stats'),
    path('provider/reviews/', ProviderRoomReviewListView.as_view(), name='provider-reviews'),

    path('admin/bookings/', SuperAdminRoomBookingListView.as_view(), name='admin-bookings'),
    path('admin/bookings/<int:pk>/', SuperAdminRoomBookingDetailView.as_view(), name='admin-booking-detail'),
    path('admin/bookings/<int:pk>/payment-status/', SuperAdminRoomPaymentStatusView.as_view(), name='admin-booking-payment-status'),
]
