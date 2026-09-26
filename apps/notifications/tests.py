from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role
from apps.academics.models import (
    AssignmentType,
    ClassSubjectAssignment,
    EducationLevel,
    LevelGroup,
    SchoolClass,
    Subject,
    SubjectLevel,
    SubjectTypeForLevel,
    TeacherAssignment,
)
from apps.staff.models import Teacher

from .models import BroadcastScope, Notification


class NotificationSecurityTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.teacher_one = users.create_user(username="teacher-one", password="pass", role=Role.TEACHER)
        self.teacher_two = users.create_user(username="teacher-two", password="pass", role=Role.TEACHER)
        self.dos = users.create_user(username="dos", password="pass", role=Role.DOS)
        self.teacher_one_profile = Teacher.objects.create(
            user=self.teacher_one, phone="1", join_date=date(2024, 1, 1),
        )
        self.teacher_two_profile = Teacher.objects.create(
            user=self.teacher_two, phone="2", join_date=date(2024, 1, 1),
        )
        self.client = APIClient()

    def test_teacher_cannot_broadcast_to_all_teachers(self):
        self.client.force_authenticate(self.teacher_one)
        response = self.client.post(
            "/api/notifications/",
            {"broadcast_scope": BroadcastScope.ALL_TEACHERS, "title": "Title", "message": "Message"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_broadcast_read_state_is_per_user(self):
        notification = Notification.objects.create(
            broadcast_scope=BroadcastScope.ALL_TEACHERS, title="Title", message="Message"
        )
        self.client.force_authenticate(self.teacher_one)
        marked = self.client.post(f"/api/notifications/{notification.id}/mark-read/")
        self.assertEqual(marked.status_code, 200)
        self.assertTrue(marked.data["read"])

        self.client.force_authenticate(self.teacher_two)
        listing = self.client.get("/api/notifications/")
        self.assertFalse(listing.data["results"][0]["read"])

    def test_dos_can_broadcast_to_all_teachers(self):
        self.client.force_authenticate(self.dos)
        response = self.client.post(
            "/api/notifications/",
            {"broadcast_scope": BroadcastScope.ALL_TEACHERS, "title": "Title", "message": "Message"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_teacher_cannot_message_unrelated_teacher(self):
        self.client.force_authenticate(self.teacher_one)
        response = self.client.post(
            "/api/notifications/",
            {
                "broadcast_scope": BroadcastScope.SPECIFIC_USER,
                "recipient": self.teacher_two.id,
                "title": "Title",
                "message": "Message",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_class_teacher_can_message_teacher_assigned_to_their_class(self):
        school_class = SchoolClass.objects.create(
            name="Senior 1 A", level_group=LevelGroup.SENIOR_1, stream="A",
            level=EducationLevel.O_LEVEL, class_teacher=self.teacher_one_profile,
        )
        subject = Subject.objects.create(
            subject_code="NOT-MAT", name="Mathematics", o_level_type=SubjectTypeForLevel.COMPULSORY,
            a_level_type=SubjectTypeForLevel.NOT_APPLICABLE, level=SubjectLevel.O_LEVEL,
        )
        assignment = ClassSubjectAssignment.objects.create(
            school_class=school_class, subject=subject, type=AssignmentType.COMPULSORY,
        )
        TeacherAssignment.objects.create(
            class_subject_assignment=assignment, teacher=self.teacher_two_profile, papers=[],
        )

        self.client.force_authenticate(self.teacher_one)
        response = self.client.post(
            "/api/notifications/",
            {
                "broadcast_scope": BroadcastScope.SPECIFIC_USER,
                "recipient": self.teacher_two.id,
                "title": "Results reviewed",
                "message": "Your class results were reviewed.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
