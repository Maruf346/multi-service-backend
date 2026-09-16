import logging

from django.contrib.auth import get_user_model, authenticate
from drf_spectacular.utils import extend_schema_field
from rest_framework.serializers import ModelSerializer
from rest_framework import serializers
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError


logger = logging.getLogger(__name__)

User = get_user_model()


# ── Safe public representation ─────────────────────────────────────────────

class UserPublicSerializer(serializers.ModelSerializer):
    """
    Safe read-only representation of a user for API responses.
    Never exposes passwords, is_staff, or is_superuser.
    Includes profile_picture as an absolute URL.
    """
    profile_picture = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'email', 'full_name', 'role', 'is_active', 'profile_picture']
        read_only_fields = fields

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_profile_picture(self, obj):
        if not obj.profile_picture:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.profile_picture.url)
        return obj.profile_picture.url


# ── Profile update ─────────────────────────────────────────────────────────

class UpdateProfileSerializer(serializers.Serializer):
    """
    Used by any authenticated user to update their own profile.
    Supports multipart/form-data for profile picture upload.
    """
    full_name = serializers.CharField(max_length=150, required=False)
    profile_picture = serializers.ImageField(required=False, allow_null=True)

    def update(self, instance, validated_data):
        if 'full_name' in validated_data:
            instance.full_name = validated_data['full_name']
        if 'profile_picture' in validated_data:
            instance.profile_picture = validated_data['profile_picture']
        instance.save(update_fields=[k for k in validated_data if k in ('full_name', 'profile_picture')])
        return instance


# ── Authentication serializers ──────────────────────────────────────────────

from rest_framework.exceptions import AuthenticationFailed


# ==================== REGISTRATION SERIALIZERS ====================
class InitiateRegistrationSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150, required=True)
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    confirm_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password confirmation is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    
    def validate_email(self, value):
        value = value.lower().strip()    # strip() removes any leading, and trailing whitespaces
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError('This email is already registered')
        return value
    
    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken')
        return value
    

class VerifyRegistrationOTPSerializer(serializers.Serializer):
    # Serializer for verifying OTP and completing registration
    
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    otp = serializers.CharField(
        min_length = 6,
        max_length = 6,
        required = True,
        error_messages={
            'required': 'OTP is required',
            'min_length': 'OTP must be 6 digits',
            'max_length': 'OTP must be 6 digits'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError('OTP must contain only numbers')
        return value
    
    
# ==================== PASSWORD RESET SERIALIZERS ====================

class InitiatePasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    

class VerifyPasswordResetOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(
        required=True,
        error_messages={
            'required': 'Email is required',
            'invalid': 'Enter a valid email address'
        }
    )
    otp = serializers.CharField(
        min_length=6,
        max_length=6,
        required=True,
        error_messages={
            'required': 'OTP is required',
            'min_length': 'OTP must be 6 digits',
            'max_length': 'OTP must be 6 digits'
        }
    )
    
    def validate_email(self, value):
        return value.lower().strip()
    
    def validate_otp(self, value):
        if not value.isdigit():
            raise serializers.ValidationError("OTP must contain only numbers")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    # Serializer for resetting password with token
    reset_token = serializers.CharField(
        required=True,
        error_messages={
            'required': 'Reset token is required'
        }
    )
    new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'New password is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    confirm_new_password = serializers.CharField(
        min_length=8,
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        error_messages={
            'required': 'Password confirmation is required',
            'min_length': 'Password must be at least 8 characters'
        }
    )
    
    def validate(self, data):
        if data['new_password'] != data['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': "Passwords do not match"
            })
        
        # Validate password strength
        try:
            validate_password(data['new_password'])
        except DjangoValidationError as e:
            raise serializers.ValidationError({'new_password': list(e.messages)})
        
        return data

       
class UserLoginSerializer(ModelSerializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ('email', 'password')

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError({
                "detail": "Email and password are required."
            })

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Check password first
        if not user.check_password(password):
            raise serializers.ValidationError({
                "detail": "Invalid email or password."
            })

        # Then check active
        if not user.is_active:
            raise serializers.ValidationError({
                "detail": "User account is disabled."
            })

        data['user'] = user
        return data    
        

class SuperAdminLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        from django.contrib.auth import authenticate

        user = authenticate(
            request=self.context.get('request'),
            email=data['email'],
            password=data['password']
        )

        if not user:
            raise serializers.ValidationError({
                'detail': 'Invalid email or password.'
            })

        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'This account has been deactivated.'
            })

        # Block plain employees from dashboard
        if not user.is_staff and not user.is_superuser:
            raise serializers.ValidationError({
                'detail': 'You do not have permission to access the dashboard.'
            })

        data['user'] = user
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        write_only=True,
        help_text='The JWT refresh token to blacklist.',
    )


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
    )
    new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
    )
    confirm_new_password = serializers.CharField(
        write_only=True,
        min_length=8,
        style={'input_type': 'password'},
        help_text='Must match new_password exactly.',
    )

    def validate_new_password(self, value):
        from django.contrib.auth.password_validation import validate_password
        validate_password(value)
        return value

    def validate(self, attrs):
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError({
                'confirm_new_password': 'New password and confirmation do not match.'
            })
        return attrs


class UserSerializer(ModelSerializer):
    role = serializers.CharField(read_only=True)
    onboarding_complete = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'full_name', 'email', 'username', 'phone',
            'profile_picture', 'birth_date', 'is_active',
            'role', 'onboarding_complete',
            'provider', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'is_active', 'email', 'provider', 'created_at', 'updated_at']

    def get_onboarding_complete(self, obj):
        # TODO: Implement actual onboarding logic.
        pass


# ==================== AUTHENTICATION RESPONSE SERIALIZERS ====================

class AuthTokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()
    
    
class RegistrationResponseSerializer(serializers.Serializer):
    # Serializer for registration completion response
    message = serializers.CharField()
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()
    user = UserSerializer()
    
    
