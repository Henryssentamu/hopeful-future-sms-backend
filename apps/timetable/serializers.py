from rest_framework import serializers

from .models import TimetableConfig, TimetablePeriod, TimetableSlot
from .services import find_conflicts


class TimetablePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetablePeriod
        fields = ["id", "config", "order", "label", "start_time", "end_time", "is_break", "break_label"]


class TimetableSlotSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True, default=None)
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True, default=None)
    class_name = serializers.CharField(source="school_class.name", read_only=True, default=None)

    class Meta:
        model = TimetableSlot
        fields = [
            "id", "config", "day", "period_index", "subject", "subject_name", "paper",
            "teacher", "teacher_name", "school_class", "class_name", "room", "is_break", "break_label",
        ]

    def _resolve(self, attrs, field):
        return attrs.get(field, getattr(self.instance, field, None))

    def validate(self, attrs):
        config = self._resolve(attrs, "config")
        teacher = self._resolve(attrs, "teacher")
        school_class = self._resolve(attrs, "school_class")
        conflicts = find_conflicts(
            config_id=config.id,
            day=self._resolve(attrs, "day"),
            period_index=self._resolve(attrs, "period_index"),
            teacher_id=teacher.id if teacher else None,
            room=self._resolve(attrs, "room") or "",
            school_class_id=school_class.id if school_class else None,
            exclude_id=self.instance.id if self.instance else None,
        )
        if conflicts:
            raise serializers.ValidationError({"conflicts": conflicts})
        return attrs


class TimetableConfigSerializer(serializers.ModelSerializer):
    periods = TimetablePeriodSerializer(many=True, read_only=True)
    slots = TimetableSlotSerializer(many=True, read_only=True)

    class Meta:
        model = TimetableConfig
        fields = ["id", "name", "days", "rooms", "created_at", "periods", "slots"]
