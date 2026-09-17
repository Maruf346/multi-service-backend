from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    # Auth (login / logout / refresh)
    path('auth/', include('apps.users.auth_urls')),

    # User profile + account management
    path('users/', include('apps.users.urls')),

    # Providers
    path('providers/', include(('apps.providers.urls', 'providers'), namespace='providers')),

    # Notifications
    path('notifications/', include('apps.notifications.urls')),

    # API schema and documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
