from datetime import date
from unittest.mock import patch
import warnings

from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase
from rest_framework.test import APIClient
from django.core.paginator import UnorderedObjectListWarning

from apps.accounts.models import Role
from apps.staff.models import Teacher

from .models import Department, EducationLevel, LevelGroup, SchoolClass


class AcademicAuthorizationTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.hr = users.create_user(username="hr-academics", password="pass", role=Role.HR)
        self.bursar = users.create_user(username="bursar-academics", password="pass", role=Role.BURSAR)
        self.non_teaching = users.create_user(
            username="staff-academics", password="pass", role=Role.NON_TEACHING,
        )
        teacher_user = users.create_user(username="teacher-assignee", password="pass", role=Role.TEACHER)
        self.teacher = Teacher.objects.create(user=teacher_user, phone="1", join_date=date(2024, 1, 1))
        self.school_class = SchoolClass.objects.create(
            name="Senior 1 A", level_group=LevelGroup.SENIOR_1, stream="A", level=EducationLevel.O_LEVEL,
        )
        self.client = APIClient()

    def test_hr_can_assign_class_teacher_but_cannot_change_class_identity(self):
        self.client.force_authenticate(self.hr)
        assign = self.client.patch(
            f"/api/academics/classes/{self.school_class.id}/",
            {"class_teacher": self.teacher.id}, format="json",
        )
        self.assertEqual(assign.status_code, 200)

        rename = self.client.patch(
            f"/api/academics/classes/{self.school_class.id}/",
            {"name": "Changed"}, format="json",
        )
        self.assertEqual(rename.status_code, 403)

    def test_hr_reassigns_class_teacher_atomically(self):
        previous_class = SchoolClass.objects.create(
            name="Senior 2 A", level_group=LevelGroup.SENIOR_2, stream="A",
            level=EducationLevel.O_LEVEL, class_teacher=self.teacher,
        )
        self.client.force_authenticate(self.hr)

        response = self.client.post(
            f"/api/academics/classes/{self.school_class.id}/reassign-class-teacher/",
            {"teacher_id": self.teacher.id}, format="json",
        )

        self.assertEqual(response.status_code, 200)
        previous_class.refresh_from_db()
        self.school_class.refresh_from_db()
        self.assertIsNone(previous_class.class_teacher_id)
        self.assertEqual(self.school_class.class_teacher_id, self.teacher.id)

    def test_bursar_cannot_reassign_class_teacher(self):
        self.client.force_authenticate(self.bursar)

        response = self.client.post(
            f"/api/academics/classes/{self.school_class.id}/reassign-class-teacher/",
            {"teacher_id": self.teacher.id}, format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.school_class.refresh_from_db()
        self.assertIsNone(self.school_class.class_teacher_id)

    def test_reassignment_rolls_back_if_target_save_fails(self):
        previous_class = SchoolClass.objects.create(
            name="Senior 2 A", level_group=LevelGroup.SENIOR_2, stream="A",
            level=EducationLevel.O_LEVEL, class_teacher=self.teacher,
        )
        self.client.force_authenticate(self.hr)

        with patch.object(SchoolClass, "save", side_effect=DatabaseError("forced failure")):
            with self.assertRaises(DatabaseError):
                self.client.post(
                    f"/api/academics/classes/{self.school_class.id}/reassign-class-teacher/",
                    {"teacher_id": self.teacher.id}, format="json",
                )

        previous_class.refresh_from_db()
        self.school_class.refresh_from_db()
        self.assertEqual(previous_class.class_teacher_id, self.teacher.id)
        self.assertIsNone(self.school_class.class_teacher_id)

    def test_hr_can_manage_departments(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post(
            "/api/academics/departments/",
            {"name": "Sciences", "subjects": [], "head_teacher": self.teacher.id}, format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Department.objects.filter(name="Sciences").exists())

    def test_hr_cannot_change_class_subject_allocations(self):
        self.client.force_authenticate(self.hr)
        response = self.client.post(
            f"/api/academics/classes/{self.school_class.id}/assign-teacher/",
            {"subject_id": 999, "teacher_id": self.teacher.id, "papers": []}, format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_teacher_can_read_required_academic_reference_data(self):
        self.client.force_authenticate(self.teacher.user)
        with warnings.catch_warnings():
            warnings.simplefilter("error", UnorderedObjectListWarning)
            for path in (
                "/api/academics/classes/",
                "/api/academics/subjects/",
                "/api/academics/result-windows/",
                "/api/academics/report-card-configs/",
            ):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_bursar_can_read_classes_but_not_subjects(self):
        self.client.force_authenticate(self.bursar)
        self.assertEqual(self.client.get("/api/academics/classes/").status_code, 200)
        self.assertEqual(self.client.get("/api/academics/subjects/").status_code, 403)

    def test_non_teaching_staff_cannot_read_academic_collections(self):
        self.client.force_authenticate(self.non_teaching)
        self.assertEqual(self.client.get("/api/academics/classes/").status_code, 403)
        self.assertEqual(self.client.get("/api/academics/departments/").status_code, 403)
