from rest_framework import serializers
from .models import *
# from user.serializers import UserSerializer


class SupportTicketCreateSerializer(serializers.ModelSerializer):
    """Used by authenticated users to submit support tickets"""

    class Meta:
        model = SupportTicket
        fields = ['id', 'subject', 'email', 'message', 'attachment', 'created_at']
        read_only_fields = ['id', 'created_at']



class SupportTicketAdminSerializer(serializers.ModelSerializer):
    """Used by admin for full CRUD"""

    class Meta:
        model = SupportTicket
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']
        
        