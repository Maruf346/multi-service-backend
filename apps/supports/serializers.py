from rest_framework import serializers
from .models import *
# from user.serializers import UserSerializer


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Used by authenticated users to submit support tickets"""

    class Meta:
        model = SupportTicket
        fields = ['id', 'subject', 'email', 'message', 'attachment', 'status', 'created_at']
        read_only_fields = ['id', 'status', 'created_at']



class SupportTicketAdminSerializer(serializers.ModelSerializer):
    """Used by admin for full CRUD"""

    class Meta:
        model = SupportTicket
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
        
        
class SupportTicketStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=SupportTicketStatus.choices)

    def validate_status(self, value):
        if value != SupportTicketStatus.RESOLVED:
            raise serializers.ValidationError('SuperAdmin can only mark support tickets as resolved.')
        return value


class SupportTicketAdminListResponseSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    next = serializers.URLField(allow_null=True)
    previous = serializers.URLField(allow_null=True)
    results = SupportTicketAdminSerializer(many=True)