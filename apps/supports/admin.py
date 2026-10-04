from django.contrib import admin
from django.core.exceptions import ValidationError
from .models import *


# ==============================
# Singleton Base Admin
# ==============================

class SingletonAdmin(admin.ModelAdmin):
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        # Prevent adding more than one instance
        if self.model.objects.exists():
            return False
        return True

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion (optional but recommended for singleton models)
        return False


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("email", "subject", "created_at")
    search_fields = ("email", "subject", "message")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)