from django.urls import path

from .views import ChangePasswordView, FavoriteListView, FavoriteToggleView, MeView, UpdateProfileView

app_name = 'users'

urlpatterns = [
    path('me/', MeView.as_view(), name='me'),
    path('me/update/', UpdateProfileView.as_view(), name='me-update'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('favorites/', FavoriteListView.as_view(), name='favorites'),
    path('favorites/toggle/', FavoriteToggleView.as_view(), name='favorites-toggle'),
]
