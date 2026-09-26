import threading
from datetime import date, time

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.academics.models import AssignmentType, ClassSubjectAssignment, EducationLevel, LevelGroup, SchoolClass, Subject, SubjectLevel, SubjectTypeForLevel, TeacherAssignment
from apps.accounts.models import Role
from apps.staff.models import Teacher

from .models import TimetableConfig, TimetablePeriod


class TimetableIntegrityTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.user = get_user_model().objects.create_user(username="dos-tt", password="pass", role=Role.DOS)
        teacher_user = get_user_model().objects.create_user(username="teacher-tt", password="pass", role=Role.TEACHER)
        self.teacher = Teacher.objects.create(user=teacher_user, phone="1", join_date=date(2025, 1, 1))
        self.school_class = SchoolClass.objects.create(name="Senior 2 A", level_group=LevelGroup.SENIOR_2, stream="A", level=EducationLevel.O_LEVEL)
        self.subject = Subject.objects.create(subject_code="TT-MAT", name="Timetable Mathematics", o_level_type=SubjectTypeForLevel.COMPULSORY, a_level_type=SubjectTypeForLevel.NOT_APPLICABLE, level=SubjectLevel.O_LEVEL)
        assignment = ClassSubjectAssignment.objects.create(school_class=self.school_class, subject=self.subject, type=AssignmentType.COMPULSORY)
        TeacherAssignment.objects.create(class_subject_assignment=assignment, teacher=self.teacher, papers=[])
        self.config = TimetableConfig.objects.create(name="Term timetable", days=["Monday"], rooms=["Room 1"])
        TimetablePeriod.objects.create(config=self.config, order=0, label="Period 1", start_time=time(8), end_time=time(9))
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def payload(self, **overrides):
        data = {"config": self.config.id, "day": "Monday", "period_index": 0, "subject": self.subject.id, "paper": "", "teacher": self.teacher.id, "school_class": self.school_class.id, "room": "Room 1", "is_break": False, "break_label": ""}
        data.update(overrides)
        return data

    def test_rejects_day_and_room_outside_configuration(self):
        self.assertEqual(self.client.post("/api/timetable/slots/", self.payload(day="Sunday"), format="json").status_code, 400)
        self.assertEqual(self.client.post("/api/timetable/slots/", self.payload(room="Unknown"), format="json").status_code, 400)

    def test_rejects_teacher_without_class_subject_assignment(self):
        other_user = get_user_model().objects.create_user(username="other-tt", password="pass", role=Role.TEACHER)
        other = Teacher.objects.create(user=other_user, phone="2", join_date=date(2025, 1, 1))
        self.assertEqual(self.client.post("/api/timetable/slots/", self.payload(teacher=other.id), format="json").status_code, 400)

    def test_conflicting_slot_is_rejected(self):
        first = self.client.post("/api/timetable/slots/", self.payload(), format="json")
        second = self.client.post("/api/timetable/slots/", self.payload(), format="json")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
        self.assertIn("conflicts", second.data)

    def test_concurrent_conflicting_slots_create_only_one_booking(self):
        barrier = threading.Barrier(2)
        statuses = []

        def create_slot():
            close_old_connections()
            client = APIClient()
            client.force_authenticate(get_user_model().objects.get(pk=self.user.pk))
            barrier.wait()
            statuses.append(client.post("/api/timetable/slots/", self.payload(), format="json").status_code)
            close_old_connections()

        threads = [threading.Thread(target=create_slot) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(statuses), [201, 400])

    def test_period_end_must_follow_start(self):
        response = self.client.post("/api/timetable/periods/", {"config": self.config.id, "order": 1, "label": "Bad", "start_time": "10:00", "end_time": "09:00", "is_break": False, "break_label": ""}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_used_period_and_room_cannot_be_orphaned(self):
        slot = self.client.post("/api/timetable/slots/", self.payload(), format="json")
        self.assertEqual(slot.status_code, 201)
        period = self.config.periods.get(order=0)
        self.assertEqual(self.client.delete(f"/api/timetable/periods/{period.id}/").status_code, 400)
        response = self.client.patch(
            f"/api/timetable/configs/{self.config.id}/", {"rooms": ["Room 2"]}, format="json"
        )
        self.assertEqual(response.status_code, 400)
