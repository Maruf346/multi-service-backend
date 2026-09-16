from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail


@shared_task(bind=True, max_retries=3)
def send_registration_otp_email(self, email, otp, full_name):
    subject = 'Verify your Multi-Service account'
    greeting = full_name or 'there'
    message = f'Hi {greeting},\n\nYour registration verification code is {otp}. It expires in 5 minutes.'
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_reset_otp_email(self, email, otp, full_name):
    subject = 'Reset your Multi-Service password'
    greeting = full_name or 'there'
    message = f'Hi {greeting},\n\nYour password reset code is {otp}. It expires in 10 minutes.'
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, email, full_name):
    subject = 'Welcome to Multi-Service'
    greeting = full_name or 'there'
    message = f'Hi {greeting},\n\nWelcome to Multi-Service.'
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=False)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
