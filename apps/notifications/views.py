from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role

from .models import BroadcastScope, Notification
from .serializers import NotificationSerializer


class NotificationViewSet(viewsets.ModelViewSet):
    """
    GET returns only notifications relevant to the current user: their own
    (SPECIFIC_USER), plus ALL_TEACHERS if they're a Teacher, plus DOS if
    they're DOS/Admin — mirrors how the frontend's contexts each filtered
    the same flat `notifications` array ad hoc per consuming page.
    """

    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        scopes = Q(recipient=user)
        if user.role == Role.TEACHER:
            scopes |= Q(broadcast_scope=BroadcastScope.ALL_TEACHERS)
        if user.role in (Role.DOS, Role.ADMIN, Role.HEADMASTER) or user.is_superuser:
            scopes |= Q(broadcast_scope=BroadcastScope.DOS)
        return Notification.objects.filter(scopes)

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        notification.read = True
        notification.save(update_fields=["read"])
        return Response(NotificationSerializer(notification).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        self.get_queryset().update(read=True)
        return Response({"detail": "All marked read."})
