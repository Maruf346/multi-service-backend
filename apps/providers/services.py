from django.core.exceptions import ValidationError
from django.db import transaction

from apps.notifications.services import NotificationTemplates, safe_notify
from apps.users.models import UserRole
from .models import ProviderOnboardingStatus, get_provider_profile_for_user


class ProviderProfileService:
    @staticmethod
    @transaction.atomic
    def upsert_profile(user, model_class, validated_data, mark_incomplete=True):
        existing = get_provider_profile_for_user(user)
        if existing and not isinstance(existing, model_class):
            raise ValidationError('A provider account can only have one provider profile type.')

        created = existing is None
        profile = existing or model_class(user=user)
        for field, value in validated_data.items():
            setattr(profile, field, value)

        if mark_incomplete and profile.onboarding_status != ProviderOnboardingStatus.COMPLETED:
            profile.onboarding_status = ProviderOnboardingStatus.INCOMPLETE
            profile.submitted_at = None
            profile.reviewed_at = None
            profile.reviewed_by = None
            profile.review_note = ''

        profile.full_clean()
        profile.save()

        if user.role != UserRole.SERVICE_PROVIDER:
            user.role = UserRole.SERVICE_PROVIDER
            user.save(update_fields=['role', 'updated_at'])
        return profile, created

    @staticmethod
    @transaction.atomic
    def submit_profile(user, model_class, validated_data):
        profile, created = ProviderProfileService.upsert_profile(
            user=user,
            model_class=model_class,
            validated_data=validated_data,
            mark_incomplete=False,
        )
        if profile.onboarding_status == ProviderOnboardingStatus.COMPLETED:
            raise ValidationError('Completed provider profiles cannot be resubmitted.')
        profile.submit_for_review()
        safe_notify(
            NotificationTemplates.provider_onboarding_submitted,
            provider_user=profile.user,
            service_category=profile.service_category,
            reference_id=profile.id,
        )
        return profile, created

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
