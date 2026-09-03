from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "recipient", "broadcast_scope", "title", "message", "created_at", "read"]
        read_only_fields = ["created_at"]
