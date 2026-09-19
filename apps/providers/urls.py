from django.urls import path

from .views import (
    CourierProviderProfileView,
    CourierProviderSubmitView,
    PropertyProviderProfileView,
    PropertyProviderSubmitView,
    RentalProviderProfileView,
    RentalProviderSubmitView,
    RestaurantProviderProfileView,
    RestaurantProviderSubmitView,
    RideProviderProfileView,
    RideProviderSubmitView,
    SuperAdminCourierProviderProfileDetailView,
    SuperAdminCourierProviderProfileListView,
    SuperAdminPropertyProviderProfileDetailView,
    SuperAdminPropertyProviderProfileListView,
    SuperAdminProviderApproveView,
    SuperAdminProviderProfileDetailView,
    SuperAdminProviderProfileListView,
    SuperAdminProviderRejectView,
    SuperAdminRentalProviderProfileDetailView,
    SuperAdminRentalProviderProfileListView,
    SuperAdminRestaurantProviderProfileDetailView,
    SuperAdminRestaurantProviderProfileListView,
    SuperAdminRideProviderProfileDetailView,
    SuperAdminRideProviderProfileListView,
)

app_name = 'providers'

urlpatterns = [
    path('rides/me/', RideProviderProfileView.as_view(), name='rides-me'),
    path('rides/me/submit/', RideProviderSubmitView.as_view(), name='rides-submit'),
    path('restaurants/me/', RestaurantProviderProfileView.as_view(), name='restaurants-me'),
    path('restaurants/me/submit/', RestaurantProviderSubmitView.as_view(), name='restaurants-submit'),
    path('courier/me/', CourierProviderProfileView.as_view(), name='courier-me'),
    path('courier/me/submit/', CourierProviderSubmitView.as_view(), name='courier-submit'),
    path('rentals/me/', RentalProviderProfileView.as_view(), name='rentals-me'),
    path('rentals/me/submit/', RentalProviderSubmitView.as_view(), name='rentals-submit'),
    path('properties/me/', PropertyProviderProfileView.as_view(), name='properties-me'),
    path('properties/me/submit/', PropertyProviderSubmitView.as_view(), name='properties-submit'),

    path('admin/rides/profiles/', SuperAdminRideProviderProfileListView.as_view(), name='admin-rides-profiles'),
    path('admin/rides/profiles/<int:pk>/', SuperAdminRideProviderProfileDetailView.as_view(), name='admin-rides-profile-detail'),
    path('admin/restaurants/profiles/', SuperAdminRestaurantProviderProfileListView.as_view(), name='admin-restaurants-profiles'),
    path('admin/restaurants/profiles/<int:pk>/', SuperAdminRestaurantProviderProfileDetailView.as_view(), name='admin-restaurants-profile-detail'),
    path('admin/courier/profiles/', SuperAdminCourierProviderProfileListView.as_view(), name='admin-courier-profiles'),
    path('admin/courier/profiles/<int:pk>/', SuperAdminCourierProviderProfileDetailView.as_view(), name='admin-courier-profile-detail'),
    path('admin/rentals/profiles/', SuperAdminRentalProviderProfileListView.as_view(), name='admin-rentals-profiles'),
    path('admin/rentals/profiles/<int:pk>/', SuperAdminRentalProviderProfileDetailView.as_view(), name='admin-rentals-profile-detail'),
    path('admin/properties/profiles/', SuperAdminPropertyProviderProfileListView.as_view(), name='admin-properties-profiles'),
    path('admin/properties/profiles/<int:pk>/', SuperAdminPropertyProviderProfileDetailView.as_view(), name='admin-properties-profile-detail'),

    path('applications/', SuperAdminProviderProfileListView.as_view(), name='applications'),
    path('applications/<str:service_category>/<int:pk>/', SuperAdminProviderProfileDetailView.as_view(), name='application-detail'),
    path('applications/<str:service_category>/<int:pk>/approve/', SuperAdminProviderApproveView.as_view(), name='application-approve'),
    path('applications/<str:service_category>/<int:pk>/reject/', SuperAdminProviderRejectView.as_view(), name='application-reject'),
]
