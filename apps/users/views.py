import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    extend_schema, OpenApiResponse, inline_serializer, OpenApiParameter,
)
from rest_framework import filters, generics, serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.users.models import UserRole
from apps.users.permissions import IsSuperAdmin
from .serializers import *
from .services import *

logger = logging.getLogger(__name__)
User = get_user_model()


# ── Login ──────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Login',
    description=(
        'Authenticate with email and password. Returns JWT access and refresh tokens, '
        'user role, profile picture URL, and password_change_required flag.'
    ),
    request=LoginSerializer,
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'access': serializers.CharField(),
                'refresh': serializers.CharField(),
                'user': UserPublicSerializer(),
                'password_change_required': serializers.BooleanField(),
            },
        ),
        400: OpenApiResponse(description='Invalid credentials or account disabled'),
    },
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get_authenticate_header(self, request):
        return 'Bearer'

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user, context={'request': request}).data,
            'password_change_required': user.password_change_required,
        }, status=status.HTTP_200_OK)


# ── Logout ─────────────────────────────────────────────────────────────────

@extend_schema(
    tags=['auth'],
    summary='Logout',
    description=(
        'Blacklist the provided refresh token. After this call, the token cannot '
        'be used to obtain new access tokens. The short-lived access token will '
        'expire naturally.'
    ),
    request=LogoutSerializer,
    responses={
        204: OpenApiResponse(description='Successfully logged out'),
        400: OpenApiResponse(description='Invalid or already-blacklisted token'),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            token = RefreshToken(serializer.validated_data['refresh'])
            token.blacklist()
        except TokenError as exc:
            raise InvalidToken({'detail': str(exc)})

        return Response(status=status.HTTP_204_NO_CONTENT)



# ── Change Password ────────────────────────────────────────────────────────

@extend_schema(
    tags=['users'],
    summary='Change password',
    description=(
        'Change the authenticated user\'s password. '
        'new_password and confirm_new_password must match. '
        'If password_change_required was True, it will be cleared after a '
        'successful change. Requires the current password for verification.'
    ),
    request=ChangePasswordSerializer,
    responses={
        200: OpenApiResponse(description='Password changed successfully'),
        400: OpenApiResponse(description='Validation error, wrong current password, or passwords do not match'),
    },
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data['current_password']):
            return Response(
                {'current_password': ['Incorrect current password.']},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(serializer.validated_data['new_password'])
        if user.password_change_required:
            user.password_change_required = False
        user.save(update_fields=['password', 'password_change_required'])

        logger.info('Password changed for user %s', user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)


# ==================== REGISTRATION VIEWS ====================

class InitiateRegistrationView(APIView):
    # Initiate registration by sending OTP to email
    permission_classes = [AllowAny]
    serializer_class = InitiateRegistrationSerializer
    
    @extend_schema(
        request=InitiateRegistrationSerializer,
        summary="Initiate user registration",
        description='Send OTP to email for user registration verification'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.initiate_registration(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                username=serializer.validated_data['username'],
                birth_date=serializer.validated_data.get('birth_date'),
            )
            
            logger.info(f'Registration initiated for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except ValueError as e:
            logger.warning(f'Registration initiation failed: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Unexpected error during registration initiation: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    
class VerifyRegistrationOTPView(APIView):
    # Verify OTP and complete user registration
    permission_classes = [AllowAny]
    serializer_class = VerifyRegistrationOTPSerializer
    
    @extend_schema(
        request=VerifyRegistrationOTPSerializer,
        summary="Verify registration OTP",
        description="Verifies the OTP sent during registration and completes user registration."
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.verify_and_complete_registration(
                email=serializer.validated_data['email'],
                otp=serializer.validated_data['otp']
            )
            
            user = result['user']
            
            response_data = {
                'message': 'Registration successful',
                'access_token': result['access_token'],
                'refresh_token': result['refresh_token'],
                'user': UserSerializer(user).data
            }
            
            logger.info(f"User registered successfully: {user.email}")
            
            # try:
            #     from .tasks import send_welcome_email
            #     send_welcome_email.delay(user.email, user.full_name)
            #     # NotificationTemplates.welcome(user)
            #     NotificationTemplates.new_user_joined(user)
            # except Exception as e:
            #     logger.error(f"Post-registration notifications failed for {user.email}: {str(e)}")
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            logger.warning(f'OTP verification failed: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'Unexpected error during OTP verification: {str(e)}')
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    
# ==================== PASSWORD RESET VIEWS ====================

class InitiatePasswordResetView(APIView):
    # Initiate password reset by sending OTP to email
    permission_classes = [AllowAny]
    serializer_class = InitiatePasswordResetSerializer
    
    @extend_schema(
        request=InitiatePasswordResetSerializer,
        summary='Initiate password reset',
        description='Send OTP to email for password reset'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.initiate_password_reset(
                email=serializer.validated_data['email']
            )
            
            logger.info(f'Password reset initiated for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f'Unexpected error during password reset initiation: {str(e)}')
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPasswordResetOTPView(APIView):
    # Verify password reset OTP and get reset token
    permission_classes = [AllowAny]
    serializer_class = VerifyPasswordResetOTPSerializer
    
    @extend_schema(
        request=VerifyPasswordResetOTPSerializer,
        summary='Verify password reset OTP',
        description='Verify OTP and receive reset token for password change'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.verify_reset_otp(
                email=serializer.validated_data['email'],
                otp=serializer.validated_data['otp']
            )
            
            logger.info(f'Password reset OTP verified for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except ValueError as v:
            logger.warning(f"Password reset OTP verification failed: {str(v)}")
            return Response(
                {'error': str(v)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error during password reset OTP verification: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ResetPasswordView(APIView):
    # Reset password using reset token
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer
    
    @extend_schema(
        request=ResetPasswordSerializer,
        summary='Reset password',
        description='Reset password using the reset token'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.reset_password(
                reset_token=serializer.validated_data['reset_token'],
                new_password=serializer.validated_data['new_password']
            )
            
            # Get user by ID from result and Send password update notification
            user_id = result.get('user_id')
            # if user_id:
            #     try:
            #         user = User.objects.get(id=user_id)
            #         NotificationTemplates.password_updated(user)
            #     except User.DoesNotExist:
            #         pass
            #     except Exception as e:
            #         logger.error(f"Failed to send notification: {str(e)}")
            
            logger.info('Password reset successful')
            return Response(
                {'message': result['message']},
                status=status.HTTP_200_OK
            )
        
        except ValueError as e:
            logger.warning(f"Password reset failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error during password reset: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )



@extend_schema(
    tags=['admin'],
    summary="Admin / Manager dashboard login",
    description="Unified login for admin and manager roles. Returns JWT tokens and user role.",
    request=SuperAdminLoginSerializer,
)
class AdminDashboardLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SuperAdminLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': f'Welcome back, {user.full_name}.',
            'user': {
                # TODO: Add user details here
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)
        
        
        
