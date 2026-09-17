from django.contrib import admin
from django.utils.html import format_html

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'user_email',
        'audience',
        'notification_type',
        'priority_badge',
        'is_read',
        'created_at',
    )
    list_filter = ('audience', 'notification_type', 'priority', 'is_read', 'created_at')
    search_fields = ('title', 'body', 'user__email', 'user__full_name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'read_at')
    ordering = ('-created_at',)
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Notification', {
            'fields': ('user', 'audience', 'notification_type', 'title', 'body', 'priority'),
        }),
        ('Payload', {
            'fields': ('data',),
            'classes': ('collapse',),
        }),
        ('Read State', {
            'fields': ('is_read', 'read_at'),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def user_email(self, obj):
        return obj.user.email

    user_email.short_description = 'User'
    user_email.admin_order_field = 'user__email'

    def priority_badge(self, obj):
        colors = {
            'low': '#6b7280',
            'normal': '#0878ff',
            'high': '#f59e0b',
            'urgent': '#dc2626',
        }
        color = colors.get(obj.priority, '#6b7280')
        return format_html(
            '<span style="background-color: {}; color: #fff; padding: 3px 10px; border-radius: 3px; font-weight: 700;">{}</span>',
            color,
            obj.get_priority_display(),
        )

    priority_badge.short_description = 'Priority'
