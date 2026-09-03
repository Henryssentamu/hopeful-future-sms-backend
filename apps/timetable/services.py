"""
Conflict detection for timetable slots — new logic (see models.py docstring),
not a port. A slot conflicts with another existing slot in the same config
if they share (day, period_index) AND the same teacher, room, or class.
"""

from .models import TimetableSlot


def find_conflicts(config_id: int, day: str, period_index: int, teacher_id=None, room="", school_class_id=None, exclude_id=None) -> list[dict]:
    base = TimetableSlot.objects.filter(config_id=config_id, day=day, period_index=period_index)
    if exclude_id:
        base = base.exclude(id=exclude_id)

    conflicts = []
    if teacher_id:
        for slot in base.filter(teacher_id=teacher_id):
            conflicts.append({"type": "teacher", "day": day, "period_index": period_index, "message": f"{slot.teacher} is already booked in this period."})
    if room:
        for slot in base.filter(room=room):
            conflicts.append({"type": "room", "day": day, "period_index": period_index, "message": f"Room {room} is already booked in this period."})
    if school_class_id:
        for slot in base.filter(school_class_id=school_class_id):
            conflicts.append({"type": "class", "day": day, "period_index": period_index, "message": f"{slot.school_class} already has a lesson in this period."})
    return conflicts
