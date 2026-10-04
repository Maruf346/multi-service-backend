from django.urls import path

from .views import AdminUserDetailView, AdminUserListView, AdminUserStatusUpdateView, ChangePasswordView, FavoriteListView, FavoriteToggleView, MeView, SuperAdminProfileView, UpdateProfileView

app_name = 'users'

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('me/update/', UpdateProfileView.as_view(), name='me-update'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('admin/users/', AdminUserListView.as_view(), name='admin-users'),
    path('admin/users/<int:pk>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<int:pk>/status/', AdminUserStatusUpdateView.as_view(), name='admin-user-status'),
    path('admin/profile/', SuperAdminProfileView.as_view(), name='admin-profile'),
    path('favorites/', FavoriteListView.as_view(), name='favorites'),
    path('favorites/toggle/', FavoriteToggleView.as_view(), name='favorites-toggle'),
]
