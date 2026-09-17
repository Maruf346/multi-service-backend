from django.urls import path

from .views import (
    ProviderProfileMeView,
    ProviderProfileSubmitView,
    SuperAdminProviderApproveView,
    SuperAdminProviderProfileDetailView,
    SuperAdminProviderProfileListView,
    SuperAdminProviderRejectView,
)

app_name = 'providers'

urlpatterns = [
    path('me/', ProviderProfileMeView.as_view(), name='me'),
    path('me/submit/', ProviderProfileSubmitView.as_view(), name='me-submit'),
    path('applications/', SuperAdminProviderProfileListView.as_view(), name='applications'),
    path('applications/<int:pk>/', SuperAdminProviderProfileDetailView.as_view(), name='application-detail'),
    path('applications/<int:pk>/approve/', SuperAdminProviderApproveView.as_view(), name='application-approve'),
    path('applications/<int:pk>/reject/', SuperAdminProviderRejectView.as_view(), name='application-reject'),
]
