from django.db import transaction

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.users.models import UserRole
from .models import ProviderApprovalStatus, ProviderProfile


class ProviderProfileService:
    @staticmethod
    @transaction.atomic
    def upsert_profile(user, validated_data):
        profile, created = ProviderProfile.objects.update_or_create(
            user=user,
            defaults=validated_data,
        )
        if user.role != UserRole.SERVICE_PROVIDER:
            user.role = UserRole.SERVICE_PROVIDER
            user.save(update_fields=['role', 'updated_at'])
        return profile, created

    @staticmethod
    @transaction.atomic
    def submit_for_review(profile):
        profile.submit_for_review()
        safe_notify(
            NotificationTemplates.provider_onboarding_submitted,
            provider_user=profile.user,
            service_category=profile.service_category,
            reference_id=profile.id,
        )
        return profile

    @staticmethod
    @transaction.atomic
    def approve(profile, reviewer, note=''):
        profile.approve(reviewer=reviewer, note=note)
        safe_notify(
            NotificationTemplates.provider_onboarding_decision,
            provider_user=profile.user,
            service_category=profile.service_category,
            approved=True,
            reason=note,
            reference_id=profile.id,
        )
        return profile

    @staticmethod
    @transaction.atomic
    def reject(profile, reviewer, note=''):
        profile.reject(reviewer=reviewer, note=note)
        safe_notify(
            NotificationTemplates.provider_onboarding_decision,
            provider_user=profile.user,
            service_category=profile.service_category,
            approved=False,
            reason=note,
            reference_id=profile.id,
        )
        return profile

    @staticmethod
    def can_submit(profile):
        return profile.approval_status in (ProviderApprovalStatus.PENDING, ProviderApprovalStatus.REJECTED)
