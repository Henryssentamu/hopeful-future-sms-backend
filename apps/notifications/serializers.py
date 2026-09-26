from rest_framework import serializers

from apps.accounts.models import Role

from .models import BroadcastScope, Notification


class NotificationSerializer(serializers.ModelSerializer):
    read = serializers.SerializerMethodField()

    def get_read(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return any(receipt.user_id == request.user.id for receipt in obj.read_receipts.all())
        return False

    class Meta:
        model = Notification
        fields = ["id", "recipient", "broadcast_scope", "title", "message", "created_at", "read"]
        read_only_fields = ["created_at", "read"]

    def validate(self, attrs):
        scope = attrs.get("broadcast_scope", getattr(self.instance, "broadcast_scope", None))
        recipient = attrs.get("recipient", getattr(self.instance, "recipient", None))
        if scope == BroadcastScope.SPECIFIC_USER and recipient is None:
            raise serializers.ValidationError({"recipient": "A recipient is required for a specific notification."})
        if scope != BroadcastScope.SPECIFIC_USER and recipient is not None:
            raise serializers.ValidationError({"recipient": "Broadcast notifications cannot have a recipient."})

        request = self.context.get("request")
        if request and request.method == "POST":
            user = request.user
            privileged = user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS)
            if scope == BroadcastScope.ALL_TEACHERS and not privileged:
                raise serializers.ValidationError({"broadcast_scope": "Only DOS or school leadership can notify all teachers."})
            if scope == BroadcastScope.DOS and user.role not in (Role.TEACHER, Role.ADMIN, Role.HEADMASTER, Role.DOS):
                raise serializers.ValidationError({"broadcast_scope": "This role cannot notify the DOS."})
            if scope == BroadcastScope.SPECIFIC_USER:
                if user.role == Role.TEACHER and recipient.role != Role.TEACHER:
                    raise serializers.ValidationError({"recipient": "Teachers may only send direct workflow notifications to teachers."})
                if user.role == Role.TEACHER and not self._teachers_share_result_workflow(user, recipient):
                    raise serializers.ValidationError(
                        {"recipient": "This teacher is not part of one of your class result workflows."}
                    )
                if not privileged and user.role != Role.TEACHER:
                    raise serializers.ValidationError({"recipient": "This role cannot send direct notifications."})
        return attrs

    @staticmethod
    def _teachers_share_result_workflow(sender, recipient):
        sender_teacher = getattr(sender, "teacher_profile", None)
        recipient_teacher = getattr(recipient, "teacher_profile", None)
        if sender_teacher is None or recipient_teacher is None:
            return False

        sender_leads_recipient = sender_teacher.class_teacher_of.filter(
            subject_assignments__teacher_assignments__teacher=recipient_teacher,
        ).exists()
        recipient_leads_sender = recipient_teacher.class_teacher_of.filter(
            subject_assignments__teacher_assignments__teacher=sender_teacher,
        ).exists()
        return sender_leads_recipient or recipient_leads_sender
