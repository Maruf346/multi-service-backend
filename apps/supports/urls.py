from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *


router = DefaultRouter()
router.register(r'admin/support-tickets', SupportTicketAdminViewSet, basename='admin-support-ticket')



urlpatterns = [
    path('', include(router.urls)),

    # Support Tickets
    path('support-tickets/submit/', SupportTicketCreateView.as_view(), name='submit-support-ticket'),
    path('support-tickets/my-tickets/', UserSupportTicketListView.as_view(), name='my-support-tickets'),
]
