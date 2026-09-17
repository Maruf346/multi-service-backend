import logging

from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    AuthTokenResponseSerializer,
    ChangePasswordSerializer,
    InitiatePasswordResetSerializer,
    InitiateRegistrationSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegistrationResponseSerializer,
    ResetPasswordSerializer,
    SuperAdminLoginSerializer,
    UpdateProfileSerializer,
    UserPublicSerializer,
    VerifyPasswordResetOTPSerializer,
    VerifyRegistrationOTPSerializer,
)
from .services import PasswordResetService, RegistrationService

logger = logging.getLogger(__name__)


@extend_schema(
    tags=['Auth'],
    summary='Refresh JWT token',
    responses={200: AuthTokenResponseSerializer},
)
class CustomTokenRefreshView(TokenRefreshView):
    pass


@extend_schema(
    tags=['Auth'],
    summary='Login',
    request=LoginSerializer,
    responses={200: AuthTokenResponseSerializer},
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary='Admin dashboard login',
    request=SuperAdminLoginSerializer,
    responses={200: AuthTokenResponseSerializer},
)
class AdminDashboardLoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = SuperAdminLoginSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        refresh = RefreshToken.for_user(user)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserPublicSerializer(user, context={'request': request}).data,
        }, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary='Logout',
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


@extend_schema(
    tags=['Auth'],
    summary='Initiate user registration',
    request=InitiateRegistrationSerializer,
    responses={200: inline_serializer(
        name='InitiateRegistrationResponse',
        fields={
            'message': serializers.CharField(),
            'email': serializers.EmailField(),
            'expires_in_seconds': serializers.IntegerField(),
        },
    )},
)
class InitiateRegistrationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = InitiateRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = RegistrationService.initiate_registration(
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password'],
            full_name=serializer.validated_data['full_name'],
            phone_number=serializer.validated_data.get('phone_number', ''),
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary='Verify registration OTP',
    request=VerifyRegistrationOTPSerializer,
    responses={201: RegistrationResponseSerializer},
)
class VerifyRegistrationOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyRegistrationOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = RegistrationService.verify_and_complete_registration(
            email=serializer.validated_data['email'],
            otp=serializer.validated_data['otp'],
        )
        return Response({
            'message': 'Registration successful.',
            'access': result['access'],
            'refresh': result['refresh'],
            'user': UserPublicSerializer(result['user'], context={'request': request}).data,
        }, status=status.HTTP_201_CREATED)


@extend_schema(
    tags=['Auth'],
    summary='Initiate password reset',
    request=InitiatePasswordResetSerializer,
    responses={200: inline_serializer(
        name='InitiatePasswordResetResponse',
        fields={
            'message': serializers.CharField(),
            'expires_in_seconds': serializers.IntegerField(),
        },
    )},
)
class InitiatePasswordResetView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = InitiatePasswordResetSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.initiate_password_reset(serializer.validated_data['email'])
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary='Verify password reset OTP',
    description='Verify the OTP sent to the user\'s email for password reset. If valid, a reset token will be returned.',
    request=VerifyPasswordResetOTPSerializer,
    responses={200: inline_serializer(
        name='VerifyPasswordResetOTPResponse',
        fields={
            'reset_token': serializers.CharField(),
            'message': serializers.CharField(),
        },
    )},
)
class VerifyPasswordResetOTPView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = VerifyPasswordResetOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.verify_reset_otp(
            email=serializer.validated_data['email'],
            otp=serializer.validated_data['otp'],
        )
        return Response(result, status=status.HTTP_200_OK)


@extend_schema(
    tags=['Auth'],
    summary='Reset password',
    description='Reset password using the reset token obtained after verifying the OTP.',
    request=ResetPasswordSerializer,
)
class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = PasswordResetService.reset_password(
            reset_token=serializer.validated_data['reset_token'],
            new_password=serializer.validated_data['new_password'],
        )
        return Response({'message': result['message']}, status=status.HTTP_200_OK)


@extend_schema(tags=['Users'], summary='Get current user profile', responses={200: UserPublicSerializer})
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserPublicSerializer(request.user, context={'request': request}).data)


@extend_schema(
    tags=['Users'],
    summary='Update current user profile',
    request=UpdateProfileSerializer,
    responses={200: UserPublicSerializer},
)
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(UserPublicSerializer(request.user, context={'request': request}).data)


@extend_schema(
    tags=['Users'],
    summary='Change password',
    description='Allows an authenticated user to change their password by providing the current password and a new password.',
    request=ChangePasswordSerializer,
    responses={200: OpenApiResponse(description='Password changed successfully')},
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
        user.save(update_fields=['password', 'updated_at'])
        logger.info('Password changed for user %s', user.email)
        return Response({'detail': 'Password changed successfully.'}, status=status.HTTP_200_OK)
