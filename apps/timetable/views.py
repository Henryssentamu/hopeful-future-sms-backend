from rest_framework import permissions, serializers, viewsets

from apps.accounts.permissions import IsDOSOrAdmin

from .models import TimetableConfig, TimetablePeriod, TimetableSlot
from .serializers import TimetableConfigSerializer, TimetablePeriodSerializer, TimetableSlotSerializer


class ReadAllWriteDOSOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return IsDOSOrAdmin().has_permission(request, view)


class TimetableConfigViewSet(viewsets.ModelViewSet):
    queryset = TimetableConfig.objects.prefetch_related("periods", "slots")
    serializer_class = TimetableConfigSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]


class TimetablePeriodViewSet(viewsets.ModelViewSet):
    queryset = TimetablePeriod.objects.select_related("config")
    serializer_class = TimetablePeriodSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["config"]

    def perform_destroy(self, instance):
        if instance.config.slots.filter(period_index=instance.order).exists():
            raise serializers.ValidationError({"detail": "Delete this period's timetable slots first."})
        instance.delete()


class TimetableSlotViewSet(viewsets.ModelViewSet):
    queryset = TimetableSlot.objects.select_related("subject", "teacher__user", "school_class")
    serializer_class = TimetableSlotSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["config", "day", "teacher", "school_class", "room"]
