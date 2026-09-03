from django.db import models

from apps.academics.models import SchoolClass, Subject
from apps.staff.models import Teacher


class TimetableConfig(models.Model):
    """
    No seed data exists for this app — the frontend's `timetables: []` is
    empty and there's no documented conflict-detection algorithm to port
    (see plan doc). An empty table after seeding is the faithful state.
    """

    name = models.CharField(max_length=150)
    days = models.JSONField(default=list, help_text='e.g. ["Monday", "Tuesday", ...]')
    rooms = models.JSONField(default=list, help_text="Room names")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class TimetablePeriod(models.Model):
    config = models.ForeignKey(TimetableConfig, on_delete=models.CASCADE, related_name="periods")
    order = models.PositiveIntegerField(help_text="Position within the day — matches TimetableSlot.period_index")
    label = models.CharField(max_length=50)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)
    break_label = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["order"]
        unique_together = [("config", "order")]

    def __str__(self):
        return f"{self.config.name} — {self.label}"


class TimetableSlot(models.Model):
    """
    New logic, not a port — the frontend never populated example data or a
    documented conflict-detection algorithm here. Conflict checks (same
    day+period, teacher/room/class double-booked) are enforced in
    timetable/services.py, called from the serializer, since NULL-inclusive
    unique_together doesn't reliably prevent this across DBs.
    """

    config = models.ForeignKey(TimetableConfig, on_delete=models.CASCADE, related_name="slots")
    day = models.CharField(max_length=20)
    period_index = models.PositiveIntegerField()
    subject = models.ForeignKey(Subject, null=True, blank=True, on_delete=models.SET_NULL)
    paper = models.CharField(max_length=20, blank=True)
    teacher = models.ForeignKey(Teacher, null=True, blank=True, on_delete=models.SET_NULL)
    school_class = models.ForeignKey(SchoolClass, null=True, blank=True, on_delete=models.SET_NULL)
    room = models.CharField(max_length=50, blank=True)
    is_break = models.BooleanField(default=False)
    break_label = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return f"{self.day} #{self.period_index} — {self.subject or self.break_label or 'slot'}"
