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
    SuperAdminProviderApproveView,
    SuperAdminProviderProfileDetailView,
    SuperAdminProviderProfileListView,
    SuperAdminProviderRejectView,
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
    path('applications/', SuperAdminProviderProfileListView.as_view(), name='applications'),
    path('applications/<str:service_category>/<int:pk>/', SuperAdminProviderProfileDetailView.as_view(), name='application-detail'),
    path('applications/<str:service_category>/<int:pk>/approve/', SuperAdminProviderApproveView.as_view(), name='application-approve'),
    path('applications/<str:service_category>/<int:pk>/reject/', SuperAdminProviderRejectView.as_view(), name='application-reject'),
]
