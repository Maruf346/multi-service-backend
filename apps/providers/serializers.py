from rest_framework import serializers

from apps.users.models import UserRole
from .models import ProviderApprovalStatus, ProviderOnboardingStatus, ProviderProfile, ProviderServiceCategory


class ProviderProfileSerializer(serializers.ModelSerializer):
    user_email = serializers.EmailField(source='user.email', read_only=True)
    user_full_name = serializers.CharField(source='user.full_name', read_only=True)
    reviewed_by_email = serializers.EmailField(source='reviewed_by.email', read_only=True)

    class Meta:
        model = ProviderProfile
        fields = [
            'id', 'user', 'user_email', 'user_full_name', 'service_category',
            'business_name', 'display_name', 'contact_phone', 'contact_email',
            'business_address', 'city', 'state', 'postal_code', 'country',
            'latitude', 'longitude', 'onboarding_status', 'approval_status',
            'submitted_at', 'reviewed_at', 'reviewed_by', 'reviewed_by_email',
            'review_note', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'user_email', 'user_full_name', 'onboarding_status',
            'approval_status', 'submitted_at', 'reviewed_at', 'reviewed_by',
            'reviewed_by_email', 'review_note', 'is_active', 'created_at', 'updated_at',
        ]


class ProviderProfileUpsertSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProviderProfile
        fields = [
            'service_category', 'business_name', 'display_name', 'contact_phone',
            'contact_email', 'business_address', 'city', 'state', 'postal_code',
            'country', 'latitude', 'longitude',
        ]
        extra_kwargs = {
            'service_category': {'required': True},
            'business_name': {'required': True},
        }

    def validate_service_category(self, value):
        if value not in ProviderServiceCategory.values:
            raise serializers.ValidationError('Invalid service category.')
        return value

    def validate(self, attrs):
        user = self.context['request'].user
        existing = getattr(user, 'provider_profile', None)
        if existing and existing.approval_status == ProviderApprovalStatus.APPROVED:
            new_category = attrs.get('service_category', existing.service_category)
            if new_category != existing.service_category:
                raise serializers.ValidationError({
                    'service_category': 'Approved providers cannot change service category.'
                })
        return attrs


class ProviderSubmitResponseSerializer(serializers.Serializer):
    detail = serializers.CharField()
    provider = ProviderProfileSerializer()


class ProviderReviewSerializer(serializers.Serializer):
    note = serializers.CharField(required=False, allow_blank=True, max_length=1000)


class ProviderProfileListSerializer(ProviderProfileSerializer):
    pass


class ProviderRegistrationGuardMixin:
    def validate_user_role(self, user):
        if user.role != UserRole.SERVICE_PROVIDER:
            raise serializers.ValidationError('Only service provider accounts can create provider profiles.')
