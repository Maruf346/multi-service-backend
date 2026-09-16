from email.mime.image import MIMEImage
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

LOGO_CID = 'multi_service_logo'
LOGO_PATH = Path(settings.BASE_DIR) / 'core' / 'logo.png'


def _expiry_minutes(seconds):
    return max(1, int(seconds) // 60)


def _attach_inline_logo(message):
    if not LOGO_PATH.exists():
        return None

    with LOGO_PATH.open('rb') as logo_file:
        image = MIMEImage(logo_file.read(), _subtype='png')
    image.add_header('Content-ID', f'<{LOGO_CID}>')
    image.add_header('Content-Disposition', 'inline', filename='logo.png')
    message.attach(image)
    return LOGO_CID


def _send_templated_email(subject, to_email, template_name, context):
    context = {
        'frontend_url': settings.FRONTEND_URL,
        'logo_cid': LOGO_CID if LOGO_PATH.exists() else None,
        **context,
    }
    text_body = render_to_string(f'users/emails/{template_name}.txt', context).strip()
    html_body = render_to_string(f'users/emails/{template_name}.html', context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[to_email],
    )
    message.attach_alternative(html_body, 'text/html')
    _attach_inline_logo(message)
    message.send(fail_silently=False)


@shared_task(bind=True, max_retries=3)
def send_registration_otp_email(self, email, otp, full_name):
    try:
        _send_templated_email(
            subject='Verify your Multi-Service account',
            to_email=email,
            template_name='registration_otp',
            context={
                'otp': otp,
                'full_name': full_name,
                'expiry_minutes': _expiry_minutes(settings.OTP_EXPIRY_SECONDS),
            },
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_password_reset_otp_email(self, email, otp, full_name):
    try:
        _send_templated_email(
            subject='Reset your Multi-Service password',
            to_email=email,
            template_name='password_reset_otp',
            context={
                'otp': otp,
                'full_name': full_name,
                'expiry_minutes': _expiry_minutes(settings.PASSWORD_RESET_OTP_EXPIRY_SECONDS),
            },
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=3)
def send_welcome_email(self, email, full_name):
    try:
        _send_templated_email(
            subject='Welcome to Multi-Service',
            to_email=email,
            template_name='welcome',
            context={'full_name': full_name},
        )
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
