from django.db.models import Q
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role

from .models import BroadcastScope, Notification, NotificationReadReceipt
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
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        user = self.request.user
        scopes = Q(recipient=user)
        if user.role == Role.TEACHER:
            scopes |= Q(broadcast_scope=BroadcastScope.ALL_TEACHERS)
        if user.role in (Role.DOS, Role.ADMIN, Role.HEADMASTER) or user.is_superuser:
            scopes |= Q(broadcast_scope=BroadcastScope.DOS)
        return Notification.objects.filter(scopes).prefetch_related("read_receipts")

    @action(detail=True, methods=["post"], url_path="mark-read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        NotificationReadReceipt.objects.get_or_create(notification=notification, user=request.user)
        notification._prefetched_objects_cache.pop("read_receipts", None)
        return Response(NotificationSerializer(notification, context={"request": request}).data)

    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        NotificationReadReceipt.objects.bulk_create(
            [NotificationReadReceipt(notification=notification, user=request.user) for notification in self.get_queryset()],
            ignore_conflicts=True,
        )
        return Response({"detail": "All marked read."})
