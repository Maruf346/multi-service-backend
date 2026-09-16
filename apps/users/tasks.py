from celery import shared_task
import logging
from django.core.mail import send_mail
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3) # Task will retry up to 3 times if it fails.
def send_registration_otp_email(self, email, otp, full_name):
    # TODO: Add HTML email template for better formatting
    pass


@shared_task(bind=True, max_retries=3)
def send_password_reset_otp_email(self, email, otp, full_name):
    """
    Send OTP email for password reset
    """
    # TODO: Add HTML email template for better formatting
    subject = 'something'
    message = "something"
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,  # If email fails → raises an exception.
        )
        logger.info(f"Password reset OTP sent successfully to {email}")
    except Exception as e:
        logger.error(f"Failed to send password reset OTP to {email}: {str(e)}")
        raise self.retry(e=e, countdown=60 * (2 ** self.request.retries))
    

@shared_task
def send_welcome_email(email, full_name):
    # Send welcome email after successful registration
    
    # TODO: Add HTML email template for better formatting
    subject = 'Welcome to Swift Go'
    message = "Something"
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=True,  # Don't fail registration if welcome email fails
        )
        logger.info(f'Welcome email sent to {email}')
    except Exception as e:
        logger.error(f'Failed to send welcome email to {email}: {str(e)}')