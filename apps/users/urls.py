from django.urls import path

from .views import * 

app_name = 'users'

urlpatterns = [
    
    # TODO: Add necessary endpoints

    # ── Password management ──────────────────────────────────────────────
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),

   
]
