from django.db import transaction
from rest_framework import serializers

from apps.academics.models import ClassSubjectAssignment

from .models import TimetableConfig, TimetablePeriod, TimetableSlot
from .services import find_conflicts


class TimetablePeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimetablePeriod
        fields = ["id", "config", "order", "label", "start_time", "end_time", "is_break", "break_label"]

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        is_break = attrs.get("is_break", getattr(self.instance, "is_break", False))
        break_label = attrs.get("break_label", getattr(self.instance, "break_label", ""))
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        if is_break and not break_label.strip():
            raise serializers.ValidationError({"break_label": "A break label is required."})
        if self.instance:
            new_config = attrs.get("config", self.instance.config)
            new_order = attrs.get("order", self.instance.order)
            if (new_config.pk != self.instance.config_id or new_order != self.instance.order) and self.instance.config.slots.filter(
                period_index=self.instance.order
            ).exists():
                raise serializers.ValidationError("Cannot move a period that already has timetable slots.")
        return attrs

    def create(self, validated_data):
        with transaction.atomic():
            config = TimetableConfig.objects.select_for_update().get(pk=validated_data["config"].pk)
            if config.periods.filter(order=validated_data["order"]).exists():
                raise serializers.ValidationError({"order": "This period order already exists."})
            return super().create(validated_data)

    def update(self, instance, validated_data):
        with transaction.atomic():
            config = TimetableConfig.objects.select_for_update().get(pk=validated_data.get("config", instance.config).pk)
            order = validated_data.get("order", instance.order)
            if config.periods.filter(order=order).exclude(pk=instance.pk).exists():
                raise serializers.ValidationError({"order": "This period order already exists."})
            return super().update(instance, validated_data)


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
        subject = self._resolve(attrs, "subject")
        day = self._resolve(attrs, "day")
        period_index = self._resolve(attrs, "period_index")
        room = (self._resolve(attrs, "room") or "").strip()
        paper = (self._resolve(attrs, "paper") or "").strip()
        is_break = self._resolve(attrs, "is_break")
        break_label = (self._resolve(attrs, "break_label") or "").strip()

        if day not in config.days:
            raise serializers.ValidationError({"day": "Day is not enabled for this timetable."})
        period = config.periods.filter(order=period_index).first()
        if period is None:
            raise serializers.ValidationError({"period_index": "Period does not belong to this timetable."})
        if bool(is_break) != period.is_break:
            raise serializers.ValidationError({"is_break": "Slot type must match the configured period."})
        if is_break:
            if any((subject, teacher, school_class, room, paper)):
                raise serializers.ValidationError({"is_break": "Break slots cannot reserve lesson resources."})
            if not break_label:
                raise serializers.ValidationError({"break_label": "A break label is required."})
        else:
            missing = [name for name, value in (("subject", subject), ("teacher", teacher), ("school_class", school_class), ("room", room)) if not value]
            if missing:
                raise serializers.ValidationError({name: "This field is required for a lesson." for name in missing})
            if room not in config.rooms:
                raise serializers.ValidationError({"room": "Room is not configured for this timetable."})
            assignment = ClassSubjectAssignment.objects.filter(school_class=school_class, subject=subject).first()
            if assignment is None:
                raise serializers.ValidationError({"subject": "Subject is not assigned to this class."})
            teacher_assignment = assignment.teacher_assignments.filter(teacher=teacher).first()
            if teacher_assignment is None:
                raise serializers.ValidationError({"teacher": "Teacher is not assigned to this class and subject."})
            if paper and paper not in teacher_assignment.papers:
                raise serializers.ValidationError({"paper": "Teacher is not assigned to this paper."})

        attrs["room"] = room
        attrs["paper"] = paper
        attrs["break_label"] = break_label
        self._check_conflicts(attrs)
        return attrs

    def _check_conflicts(self, attrs):
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

    def create(self, validated_data):
        with transaction.atomic():
            TimetableConfig.objects.select_for_update().get(pk=validated_data["config"].pk)
            self._check_conflicts(validated_data)
            return super().create(validated_data)

    def update(self, instance, validated_data):
        with transaction.atomic():
            TimetableConfig.objects.select_for_update().get(pk=validated_data.get("config", instance.config).pk)
            self._check_conflicts(validated_data)
            return super().update(instance, validated_data)


class TimetableConfigSerializer(serializers.ModelSerializer):
    periods = TimetablePeriodSerializer(many=True, read_only=True)
    slots = TimetableSlotSerializer(many=True, read_only=True)

    class Meta:
        model = TimetableConfig
        fields = ["id", "name", "days", "rooms", "created_at", "periods", "slots"]

    def validate_days(self, days):
        cleaned = [day.strip() for day in days if day.strip()]
        if not cleaned:
            raise serializers.ValidationError("At least one day is required.")
        if len(cleaned) != len(set(cleaned)):
            raise serializers.ValidationError("Days must be unique.")
        return cleaned

    def validate_rooms(self, rooms):
        cleaned = [room.strip() for room in rooms if room.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise serializers.ValidationError("Rooms must be unique.")
        return cleaned

    def validate(self, attrs):
        if self.instance:
            days = attrs.get("days", self.instance.days)
            rooms = attrs.get("rooms", self.instance.rooms)
            used_days = set(self.instance.slots.values_list("day", flat=True))
            used_rooms = set(self.instance.slots.exclude(room="").values_list("room", flat=True))
            if not used_days.issubset(set(days)):
                raise serializers.ValidationError({"days": "Cannot remove a day that still has timetable slots."})
            if not used_rooms.issubset(set(rooms)):
                raise serializers.ValidationError({"rooms": "Cannot remove a room that still has timetable slots."})
        return attrs
