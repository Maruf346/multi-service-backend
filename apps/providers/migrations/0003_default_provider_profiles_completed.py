from django.db import migrations, models


PROVIDER_PROFILE_MODELS = (
    'CourierProviderProfile',
    'PropertyProviderProfile',
    'RentalProviderProfile',
    'RestaurantProviderProfile',
    'RideProviderProfile',
)


def approve_existing_provider_profiles(apps, schema_editor):
    for model_name in PROVIDER_PROFILE_MODELS:
        model = apps.get_model('providers', model_name)
        model.objects.exclude(onboarding_status='completed').update(onboarding_status='completed')


def restore_non_completed_provider_profiles(apps, schema_editor):
    for model_name in PROVIDER_PROFILE_MODELS:
        model = apps.get_model('providers', model_name)
        model.objects.filter(onboarding_status='completed', reviewed_by__isnull=True).update(onboarding_status='incomplete')


class Migration(migrations.Migration):

    dependencies = [
        ('providers', '0002_remove_courierproviderprofile_providers_c_approva_54d1ea_idx_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='courierproviderprofile',
            name='onboarding_status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('submitted', 'Submitted'), ('completed', 'Completed')], default='completed', max_length=32),
        ),
        migrations.AlterField(
            model_name='propertyproviderprofile',
            name='onboarding_status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('submitted', 'Submitted'), ('completed', 'Completed')], default='completed', max_length=32),
        ),
        migrations.AlterField(
            model_name='rentalproviderprofile',
            name='onboarding_status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('submitted', 'Submitted'), ('completed', 'Completed')], default='completed', max_length=32),
        ),
        migrations.AlterField(
            model_name='restaurantproviderprofile',
            name='onboarding_status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('submitted', 'Submitted'), ('completed', 'Completed')], default='completed', max_length=32),
        ),
        migrations.AlterField(
            model_name='rideproviderprofile',
            name='onboarding_status',
            field=models.CharField(choices=[('incomplete', 'Incomplete'), ('submitted', 'Submitted'), ('completed', 'Completed')], default='completed', max_length=32),
        ),
        migrations.RunPython(approve_existing_provider_profiles, restore_non_completed_provider_profiles),
    ]
