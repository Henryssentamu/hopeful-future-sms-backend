from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.academics.models import (
    AssignmentType,
    ClassSubjectAssignment,
    EducationLevel,
    LevelGroup,
    ResultWindow,
    SchoolClass,
    Subject,
    SubjectLevel,
    SubjectPaper,
    SubjectTypeForLevel,
    TeacherAssignment,
)
from apps.accounts.models import Role
from apps.core.models import FinanceTerm, ResultType
from apps.results.models import ResultEntry, ResultUpload, ResultUploadStatus
from apps.notifications.models import BroadcastScope, Notification
from apps.staff.models import Teacher
from apps.students.models import EnrollmentStatus, Gender, Student, TermEnrollment


class Phase2ResultSecurityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.teacher_user = user_model.objects.create_user(
            username="teacher", password="pass", role=Role.TEACHER, first_name="T", last_name="One"
        )
        self.other_teacher_user = user_model.objects.create_user(
            username="other", password="pass", role=Role.TEACHER, first_name="T", last_name="Two"
        )
        self.dos_user = user_model.objects.create_user(username="dos", password="pass", role=Role.DOS)
        self.bursar_user = user_model.objects.create_user(username="bursar", password="pass", role=Role.BURSAR)
        self.teacher = Teacher.objects.create(
            user=self.teacher_user, phone="1", join_date=date(2024, 1, 1)
        )
        self.other_teacher = Teacher.objects.create(
            user=self.other_teacher_user, phone="2", join_date=date(2024, 1, 1)
        )
        self.school_class = SchoolClass.objects.create(
            name="Senior 1 A", level_group=LevelGroup.SENIOR_1, stream="A", level=EducationLevel.O_LEVEL
        )
        self.other_class = SchoolClass.objects.create(
            name="Senior 1 B", level_group=LevelGroup.SENIOR_1, stream="B", level=EducationLevel.O_LEVEL
        )
        self.subject = Subject.objects.create(
            subject_code="MAT", name="Mathematics", o_level_type=SubjectTypeForLevel.COMPULSORY,
            a_level_type=SubjectTypeForLevel.NOT_APPLICABLE, level=SubjectLevel.O_LEVEL,
        )
        self.other_subject = Subject.objects.create(
            subject_code="ENG", name="English", o_level_type=SubjectTypeForLevel.COMPULSORY,
            a_level_type=SubjectTypeForLevel.NOT_APPLICABLE, level=SubjectLevel.O_LEVEL,
        )
        self.paper = SubjectPaper.objects.create(subject=self.subject, paper="Paper 1", label="Paper 1")
        self.other_paper = SubjectPaper.objects.create(subject=self.other_subject, paper="Paper 1", label="Paper 1")
        assignment = ClassSubjectAssignment.objects.create(
            school_class=self.school_class, subject=self.subject, type=AssignmentType.COMPULSORY
        )
        TeacherAssignment.objects.create(class_subject_assignment=assignment, teacher=self.teacher, papers=["Paper 1"])
        self.student = Student.objects.create(
            student_number="S001", name="Student One", school_class=self.school_class, gender=Gender.MALE,
            enrollment_date=date(2025, 1, 1),
        )
        self.out_of_scope_student = Student.objects.create(
            student_number="S002", name="Student Two", school_class=self.other_class, gender=Gender.FEMALE,
            enrollment_date=date(2025, 1, 1),
        )
        TermEnrollment.objects.create(
            student=self.student, school_class=self.school_class, term=FinanceTerm.TERM_1, year=2025,
            level=EducationLevel.O_LEVEL, status=EnrollmentStatus.ENROLLED,
        )
        ResultWindow.objects.create(
            result_type=ResultType.TEST, term=FinanceTerm.TERM_1, year=2025,
            opens_at=timezone.now() - timedelta(days=1), closes_at=timezone.now() + timedelta(days=1),
        )
        self.client = APIClient()

    def payload(self, **overrides):
        data = {
            "subject_id": self.subject.id,
            "paper_id": self.paper.id,
            "school_class_id": self.school_class.id,
            "term": FinanceTerm.TERM_1,
            "year": 2025,
            "result_type": ResultType.TEST,
            "weight_percent": 50,
            "entries": [{"student_id": self.student.id, "score": 72}],
        }
        data.update(overrides)
        return data

    def test_submit_rejects_duplicate_students(self):
        self.client.force_authenticate(self.teacher_user)
        response = self.client.post(
            "/api/results/uploads/",
            self.payload(entries=[
                {"student_id": self.student.id, "score": 72},
                {"student_id": self.student.id, "score": 73},
            ]),
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(ResultUpload.objects.count(), 0)

    def test_submit_rejects_wrong_subject_paper(self):
        self.client.force_authenticate(self.teacher_user)
        response = self.client.post(
            "/api/results/uploads/", self.payload(paper_id=self.other_paper.id), format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_submit_rejects_student_outside_term_class(self):
        self.client.force_authenticate(self.teacher_user)
        response = self.client.post(
            "/api/results/uploads/",
            self.payload(entries=[{"student_id": self.out_of_scope_student.id, "score": 72}]),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_teacher_cannot_list_another_teachers_unrelated_upload(self):
        upload = ResultUpload.objects.create(
            teacher=self.other_teacher, subject=self.subject, paper=self.paper, school_class=self.other_class,
            term=FinanceTerm.TERM_1, year=2025, result_type=ResultType.TEST, weight_percent=50,
            status=ResultUploadStatus.PENDING_CLASS_TEACHER,
        )
        self.client.force_authenticate(self.teacher_user)
        response = self.client.get("/api/results/uploads/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(upload.id, [row["id"] for row in response.data["results"]])

    def test_bursar_student_payload_excludes_private_academic_and_family_fields(self):
        self.client.force_authenticate(self.bursar_user)
        response = self.client.get(f"/api/students/{self.student.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("parent_info", response.data)
        self.assertNotIn("subjects", response.data)
        self.assertNotIn("performance", response.data)

    def test_bursar_cannot_read_result_uploads(self):
        self.client.force_authenticate(self.bursar_user)
        response = self.client.get("/api/results/uploads/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_dos_can_use_fast_path_outside_submission_window(self):
        ResultWindow.objects.all().delete()
        self.client.force_authenticate(self.dos_user)
        response = self.client.post(
            "/api/results/uploads/enter-and-confirm/",
            self.payload(teacher_id=self.teacher.id),
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], ResultUploadStatus.CONFIRMED)

    def test_confirm_rolls_status_back_when_result_application_fails(self):
        upload = ResultUpload.objects.create(
            teacher=self.teacher, subject=self.subject, paper=self.paper, school_class=self.school_class,
            term=FinanceTerm.TERM_1, year=2025, result_type=ResultType.TEST, weight_percent=50,
            status=ResultUploadStatus.PENDING_DOS,
        )
        ResultEntry.objects.create(upload=upload, student=self.student, score=72, grade="B")
        self.client.force_authenticate(self.dos_user)
        self.client.raise_request_exception = False
        with patch("apps.results.views.apply_result_upload", side_effect=RuntimeError("sync failed")):
            response = self.client.post(f"/api/results/uploads/{upload.id}/confirm/")
        self.assertEqual(response.status_code, 500)
        upload.refresh_from_db()
        self.assertEqual(upload.status, ResultUploadStatus.PENDING_DOS)
        self.assertEqual(Notification.objects.count(), 0)

    def test_submission_notifies_the_assigned_class_teacher_in_the_same_workflow(self):
        self.school_class.class_teacher = self.other_teacher
        self.school_class.save(update_fields=["class_teacher"])
        self.client.force_authenticate(self.teacher_user)

        response = self.client.post("/api/results/uploads/", self.payload(), format="json")

        self.assertEqual(response.status_code, 201)
        notification = Notification.objects.get()
        self.assertEqual(notification.broadcast_scope, BroadcastScope.SPECIFIC_USER)
        self.assertEqual(notification.recipient, self.other_teacher_user)
        self.assertIn("Results submitted for your review", notification.title)

    def test_class_teacher_confirmation_notifies_dos_and_submitting_teacher(self):
        self.school_class.class_teacher = self.other_teacher
        self.school_class.save(update_fields=["class_teacher"])
        upload = ResultUpload.objects.create(
            teacher=self.teacher, subject=self.subject, paper=self.paper, school_class=self.school_class,
            term=FinanceTerm.TERM_1, year=2025, result_type=ResultType.TEST, weight_percent=50,
            status=ResultUploadStatus.PENDING_CLASS_TEACHER,
        )
        ResultEntry.objects.create(upload=upload, student=self.student, score=72, grade="B")
        self.client.force_authenticate(self.other_teacher_user)

        response = self.client.post(f"/api/results/uploads/{upload.id}/class-teacher-confirm/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], ResultUploadStatus.PENDING_DOS)
        self.assertTrue(Notification.objects.filter(broadcast_scope=BroadcastScope.DOS).exists())
        self.assertTrue(Notification.objects.filter(recipient=self.teacher_user).exists())
