import random
import secrets
import string

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class OTPService:
    @staticmethod
    def generate_otp(length=6):
        return ''.join(random.choices(string.digits, k=length))

    @staticmethod
    def verify_otp(cache_key, provided_otp):
        stored_otp = cache.get(cache_key)
        if not stored_otp:
            return False, 'OTP expired or not found'
        if stored_otp != provided_otp:
            return False, 'Invalid OTP'
        cache.delete(cache_key)
        return True, 'OTP verified'


class RegistrationService:
    @staticmethod
    def initiate_registration(email, password, full_name, phone_number=''):
        if User.objects.filter(email__iexact=email).exists():
            raise ValueError('Email already registered')

        otp = OTPService.generate_otp()
        cache_key = f'registration_otp:{email}'
        cache.set(
            cache_key,
            {
                'email': email,
                'full_name': full_name,
                'phone_number': phone_number,
                'password': make_password(password),
                'otp': otp,
            },
            settings.OTP_EXPIRY_SECONDS,
        )

        try:
            from .tasks import send_registration_otp_email
            send_registration_otp_email.delay(email, otp, full_name)
        except Exception:
            # The OTP is stored; API callers can still complete verification in
            # local/dev environments that use the console email backend.
            pass

        return {
            'message': 'OTP sent to your email. Please verify to complete registration.',
            'email': email,
            'expires_in_seconds': settings.OTP_EXPIRY_SECONDS,
        }


    @staticmethod
    def verify_and_complete_registration(email, otp):
        cache_key = f'registration_otp:{email}'
        registration_data = cache.get(cache_key)

        if not registration_data:
            raise ValueError('OTP expired or invalid email')
        if registration_data['otp'] != otp:
            raise ValueError('Invalid OTP')
        if User.objects.filter(email__iexact=email).exists():
            cache.delete(cache_key)
            raise ValueError('Email already registered')

        # Create user account
        user = User.objects.create(
            email=email,
            username=email.split('@')[0],
            full_name=registration_data.get('full_name', ''),
            phone_number=registration_data.get('phone_number', ''),
            password=registration_data['password'],
            is_active=True,
            is_staff=False,
            is_superuser=False,
        )
        cache.delete(cache_key)

        refresh = RefreshToken.for_user(user)
        return {
            'user': user,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }


class PasswordResetService:
    # Service for password reset with OTP verification
    
    @staticmethod
    def initiate_password_reset(email):
        # Send OTP for password reset
        
        # Check if user exists (but don't reveal)
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return {
                'message': 'If the email exists, an OTP has been sent.',
                'expires_in_seconds': settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
            }

        otp = OTPService.generate_otp()
        cache_key = f'password_reset_otp:{email}'
        cache.set(cache_key, otp, settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS)

        from .tasks import send_password_reset_otp_email
        send_password_reset_otp_email.delay(email, otp, user.full_name or user.email)

        return {
            'message': 'If the email exists, an OTP has been sent.',
            'expires_in_seconds': settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS,
        }

    @staticmethod
    def verify_reset_otp(email, otp):
        cache_key = f'password_reset_otp:{email}'
        stored_otp = cache.get(cache_key)
        
        if not stored_otp:
            raise ValueError('OTP expired or not found')
        
        if stored_otp != otp:
            raise ValueError('Invalid OTP')

        reset_token = secrets.token_urlsafe(32)
        cache.set(
            f'password_reset_token:{reset_token}',
            email,
            settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        )
        
        # Delete OTP (one-time use)
        cache.delete(cache_key)
        
        return {
            'reset_token': reset_token,
            'message': 'OTP verified. You can now reset your password.',
            'expires_in_seconds': settings.PASSWORD_RESET_TOKEN_EXPIRY_SECONDS,
        }
        
    @staticmethod
    def reset_password(reset_token, new_password):
        # Reset pass using token
        
        token_key = f'password_reset_token:{reset_token}'
        email = cache.get(token_key)
        
        if not email:
            raise ValueError('Invalid or expired reset token')

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise ValueError('User not found')

        user.set_password(new_password)
        
        # Delete reset token
        user.save(update_fields=['password', 'updated_at'])
        cache.delete(token_key)
        
        # Optional: Invalidate all existing tokens (force re-login)
        # from rest_framework_simplejwt.tokens import RefreshToken
        # This forces user to login again with new password
        
        return {
            'message': 'Password reset successful. Please login with your new password.',
            'user_id': str(user.id),
        }
        
        