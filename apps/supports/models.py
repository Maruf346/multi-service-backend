from django.db import models
import uuid
from django_ckeditor_5.fields import CKEditor5Field
from django.core.exceptions import ValidationError
from django.conf import settings


class SupportTicketStatus(models.TextChoices):
    PENDING = 'pending', 'Pending'
    RESOLVED = 'resolved', 'Resolved'



    
class SupportTicket(models.Model):
    """
    Submitted by customers/providers via the app's support form.
    User is automatically linked from request.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='support_tickets'
    )
    subject = models.CharField(max_length=400)
    email = models.EmailField()
    message = models.TextField()
    attachment = models.FileField(upload_to='support_attachments/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=SupportTicketStatus.choices, default=SupportTicketStatus.PENDING)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Support Ticket from {self.email}: {self.subject}"

    class Meta:
        verbose_name = 'Support Ticket'
        verbose_name_plural = 'Support Tickets'
        ordering = ['-created_at']

