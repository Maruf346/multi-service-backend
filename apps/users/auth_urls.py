from django.urls import path

from .views import (
    AdminDashboardLoginView,
    CustomTokenRefreshView,
    InitiatePasswordResetView,
    InitiateRegistrationView,
    LoginView,
    LogoutView,
    ResetPasswordView,
    VerifyPasswordResetOTPView,
    VerifyRegistrationOTPView,
)

app_name = 'auth'

urlpatterns = [
    path('register/initiate/', InitiateRegistrationView.as_view(), name='register-initiate'),
    path('register/verify/', VerifyRegistrationOTPView.as_view(), name='register-verify'),
    path('login/', LoginView.as_view(), name='login'),
    path('admin/login/', AdminDashboardLoginView.as_view(), name='admin-login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='refresh'),
    path('forget-pass/initiate/', InitiatePasswordResetView.as_view(), name='forget-password-initiate'),
    path('forget-pass/verify/', VerifyPasswordResetOTPView.as_view(), name='forget-password-verify'),
    path('forget-pass/complete/', ResetPasswordView.as_view(), name='forget-password-complete'),
]
