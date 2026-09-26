from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

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
from apps.accounts.models import Role
from apps.core.models import FinanceTerm
from apps.staff.models import Teacher

from .models import EnrollmentStatus, Gender, Student, StudentSubjectEnrollment, TermEnrollment


class StudentAuthorizationTests(TestCase):
    def setUp(self):
        users = get_user_model().objects
        self.historical_teacher_user = users.create_user(
            username="historical-class-teacher", password="pass", role=Role.TEACHER,
        )
        self.current_teacher_user = users.create_user(
            username="current-class-teacher", password="pass", role=Role.TEACHER,
        )
        self.subject_teacher_user = users.create_user(
            username="subject-teacher", password="pass", role=Role.TEACHER,
        )
        self.historical_teacher = Teacher.objects.create(
            user=self.historical_teacher_user, phone="1", join_date=date(2024, 1, 1),
        )
        self.current_teacher = Teacher.objects.create(
            user=self.current_teacher_user, phone="2", join_date=date(2024, 1, 1),
        )
        self.subject_teacher = Teacher.objects.create(
            user=self.subject_teacher_user, phone="3", join_date=date(2024, 1, 1),
        )
        self.historical_class = SchoolClass.objects.create(
            name="Senior 1 A", level_group=LevelGroup.SENIOR_1, stream="A",
            level=EducationLevel.O_LEVEL, class_teacher=self.historical_teacher,
        )
        self.current_class = SchoolClass.objects.create(
            name="Senior 2 A", level_group=LevelGroup.SENIOR_2, stream="A",
            level=EducationLevel.O_LEVEL, class_teacher=self.current_teacher,
        )
        self.student = Student.objects.create(
            student_number="ST-001", name="Learner One", school_class=self.current_class,
            gender=Gender.FEMALE, enrollment_date=date(2025, 1, 1), email="private@example.com",
            religion="Private", location="Private location",
        )
        TermEnrollment.objects.create(
            student=self.student, school_class=self.historical_class, term=FinanceTerm.TERM_1,
            year=2025, level=EducationLevel.O_LEVEL, status=EnrollmentStatus.ENROLLED,
        )
        self.assigned_subject = self._create_subject("MAT", "Mathematics")
        self.other_subject = self._create_subject("ENG", "English")
        assignment = ClassSubjectAssignment.objects.create(
            school_class=self.current_class, subject=self.assigned_subject, type=AssignmentType.COMPULSORY,
        )
        TeacherAssignment.objects.create(
            class_subject_assignment=assignment, teacher=self.subject_teacher, papers=[],
        )
        StudentSubjectEnrollment.objects.create(
            student=self.student, subject=self.assigned_subject, type=AssignmentType.COMPULSORY,
        )
        StudentSubjectEnrollment.objects.create(
            student=self.student, subject=self.other_subject, type=AssignmentType.COMPULSORY,
        )
        self.client = APIClient()

    @staticmethod
    def _create_subject(code, name):
        return Subject.objects.create(
            subject_code=code, name=name, o_level_type=SubjectTypeForLevel.COMPULSORY,
            a_level_type=SubjectTypeForLevel.NOT_APPLICABLE, level=SubjectLevel.O_LEVEL,
        )

    def test_historical_class_teacher_can_update_comment(self):
        self.client.force_authenticate(self.historical_teacher_user)
        response = self.client.patch(
            f"/api/students/{self.student.id}/term-records/Term 1/2025/comment/",
            {"role": "classTeacher", "comment": "Good progress."}, format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["class_teacher_comment"], "Good progress.")

    def test_current_class_teacher_cannot_change_historical_comment(self):
        self.client.force_authenticate(self.current_teacher_user)
        response = self.client.patch(
            f"/api/students/{self.student.id}/term-records/Term 1/2025/comment/",
            {"role": "classTeacher", "comment": "Not mine."}, format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_report_card_uses_historical_class_teacher_scope(self):
        url = f"/api/students/{self.student.id}/report-card/?term=Term%201&year=2025"
        self.client.force_authenticate(self.historical_teacher_user)
        allowed = self.client.get(url)
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.data["student"]["class_name"], self.historical_class.name)

        self.client.force_authenticate(self.current_teacher_user)
        self.assertEqual(self.client.get(url).status_code, 403)

        self.client.force_authenticate(self.subject_teacher_user)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_subject_teacher_receives_only_task_focused_student_data(self):
        self.client.force_authenticate(self.subject_teacher_user)
        self.assertEqual(self.client.get("/api/students/").status_code, 403)
        response = self.client.get("/api/students/teaching-roster/")
        self.assertEqual(response.status_code, 200)
        student = response.data["results"][0]
        for private_field in ("parent_info", "email", "gender", "age", "religion", "location", "enrollment_date"):
            self.assertNotIn(private_field, student)
        self.assertEqual([row["subject"] for row in student["subjects"]], [self.assigned_subject.id])
