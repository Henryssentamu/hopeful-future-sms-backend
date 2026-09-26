from django.db import models
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsDOSOrAdmin, IsHeadmasterOrAdmin

from .models import (
    EnrollmentStatus,
    ParentInfo,
    Student,
    StudentAttendanceRecord,
    StudentSubjectEnrollment,
    TermEnrollment,
    TermRecord,
)
from .serializers import (
    ParentInfoSerializer,
    StudentAttendanceRecordSerializer,
    StudentSerializer,
    StudentFinanceSerializer,
    StudentTeacherSerializer,
    StudentSubjectEnrollmentSerializer,
    TermEnrollmentSerializer,
    TermRecordSerializer,
    UpdateCommentSerializer,
)


class ReadAllWriteDOSOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            user = request.user
            return bool(user and user.is_authenticated and (
                user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.BURSAR)
            ))
        return IsDOSOrAdmin().has_permission(request, view)


class ReadAllWriteAdminSide(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role in (
            Role.ADMIN, Role.DOS, Role.HEADMASTER, Role.TEACHER,
        )))


class ReadScopedWriteAcademicStaff(ReadAllWriteDOSOrAdmin):
    def has_permission(self, request, view):
        if request.method not in permissions.SAFE_METHODS and request.user.role == Role.TEACHER:
            return True
        return super().has_permission(request, view)


class StudentViewSet(viewsets.ModelViewSet):
    # Digit-only pk matching so this viewset's detail routes (registered at
    # the "" prefix) don't swallow sibling collections registered on the
    # same router, e.g. "parent-info/" would otherwise match `(?P<pk>...)`.
    lookup_value_regex = r"\d+"

    queryset = Student.objects.select_related("school_class", "parent_info").prefetch_related(
        "subject_enrollments__subject", "subject_enrollments__paper"
    )
    serializer_class = StudentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["school_class", "gender"]
    search_fields = ["name", "student_number"]

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.BURSAR):
            return qs
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            return qs.filter(
                models.Q(school_class__class_teacher=teacher)
                | models.Q(school_class__subject_assignments__teacher_assignments__teacher=teacher)
            ).distinct()
        return qs.none()

    def get_serializer_class(self):
        role = getattr(self.request.user, "role", None)
        if role == Role.BURSAR and self.request.method in permissions.SAFE_METHODS:
            return StudentFinanceSerializer
        if self.action == "teaching_roster":
            return StudentTeacherSerializer
        return StudentSerializer

    def get_permissions(self):
        if self.action in ("teaching_roster", "update_comment"):
            return [permissions.IsAuthenticated()]
        return super().get_permissions()

    @action(detail=False, methods=["get"], url_path="teaching-roster")
    def teaching_roster(self, request):
        if request.user.role != Role.TEACHER:
            return Response({"detail": "Teacher access only."}, status=403)

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        return Response(self.get_serializer(queryset, many=True).data)

    def get_object(self):
        if self.action != "update_comment":
            return super().get_object()

        student = Student.objects.select_related("school_class").filter(pk=self.kwargs["pk"]).first()
        if student is None:
            raise NotFound("Student not found.")
        return student

    @action(detail=True, methods=["patch"], url_path=r"term-records/(?P<term>[^/]+)/(?P<year>[0-9]+)/comment")
    def update_comment(self, request, pk=None, term=None, year=None):
        """
        PATCH /api/students/{id}/term-records/{term}/{year}/comment/
        Port of DataContext.updateReportCardComment — sets one of the three
        MANUAL-OVERRIDE comment fields. Which field is editable depends on
        the caller's role and, for classTeacher, on actually being the
        class teacher of record for that specific term (resolved via
        TermEnrollment, not the student's current class).
        """
        student = self.get_object()
        serializer = UpdateCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data["role"]
        comment = serializer.validated_data["comment"]

        user = request.user
        if role == "classTeacher":
            enrollment = TermEnrollment.objects.filter(
                student=student, term=term, year=year, status=EnrollmentStatus.ENROLLED,
            ).select_related(
                "school_class__class_teacher__user"
            ).first()
            if enrollment is None:
                return Response({"detail": "No term enrollment exists for this student and period."}, status=404)
            class_teacher = enrollment.school_class.class_teacher
            teacher_profile = getattr(user, "teacher_profile", None)
            is_class_teacher = (
                class_teacher is not None and teacher_profile is not None and class_teacher.id == teacher_profile.id
            )
            if not (user.is_superuser or is_class_teacher):
                return Response({"detail": "Not the class teacher of record for this term."}, status=403)
            field = "class_teacher_comment"
        elif role == "dos":
            if not IsDOSOrAdmin().has_permission(request, self):
                return Response({"detail": "DOS or Admin only."}, status=403)
            field = "dos_comment"
        else:  # hm
            if not IsHeadmasterOrAdmin().has_permission(request, self):
                return Response({"detail": "Headmaster or Admin only."}, status=403)
            field = "hm_comment"

        record, _ = TermRecord.objects.get_or_create(student=student, term=term, year=year)
        setattr(record, field, comment)
        record.save(update_fields=[field])
        return Response(TermRecordSerializer(record).data)


class ParentInfoViewSet(viewsets.ModelViewSet):
    queryset = ParentInfo.objects.select_related("student")
    serializer_class = ParentInfoSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS):
            return self.queryset
        return self.queryset.none()


class StudentSubjectEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = StudentSubjectEnrollment.objects.select_related("student", "subject", "paper")
    serializer_class = StudentSubjectEnrollmentSerializer
    permission_classes = [ReadScopedWriteAcademicStaff]
    filterset_fields = ["student", "subject", "status"]

    def get_queryset(self):
        return _academic_student_scope(self.queryset, self.request.user)

    def perform_create(self, serializer):
        student = serializer.validated_data["student"]
        _require_class_teacher_or_academic_lead(self.request.user, student.school_class_id)
        serializer.save()

    def perform_update(self, serializer):
        student = serializer.validated_data.get("student", serializer.instance.student)
        _require_class_teacher_or_academic_lead(self.request.user, student.school_class_id)
        serializer.save()

    def perform_destroy(self, instance):
        _require_class_teacher_or_academic_lead(self.request.user, instance.student.school_class_id)
        instance.delete()


class TermEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = TermEnrollment.objects.select_related("student", "school_class")
    serializer_class = TermEnrollmentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student", "term", "year", "status"]

    def get_queryset(self):
        return _academic_student_scope(self.queryset, self.request.user)


class TermRecordViewSet(viewsets.ModelViewSet):
    queryset = TermRecord.objects.select_related("student").prefetch_related("marks__subject")
    serializer_class = TermRecordSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student", "term", "year"]

    def get_queryset(self):
        return _academic_student_scope(self.queryset, self.request.user)


class StudentAttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = StudentAttendanceRecord.objects.select_related("student", "school_class")
    serializer_class = StudentAttendanceRecordSerializer
    permission_classes = [ReadAllWriteAdminSide]
    filterset_fields = ["student", "school_class", "date"]

    def get_queryset(self):
        return _academic_student_scope(self.queryset, self.request.user)

    def perform_create(self, serializer):
        school_class = serializer.validated_data["school_class"]
        student = serializer.validated_data["student"]
        if student.school_class_id != school_class.id:
            raise PermissionDenied("Student is not in the selected class.")
        _require_class_teacher_or_academic_lead(self.request.user, school_class.id)
        serializer.save()

    def perform_update(self, serializer):
        school_class = serializer.validated_data.get("school_class", serializer.instance.school_class)
        student = serializer.validated_data.get("student", serializer.instance.student)
        if student.school_class_id != school_class.id:
            raise PermissionDenied("Student is not in the selected class.")
        _require_class_teacher_or_academic_lead(self.request.user, school_class.id)
        serializer.save()

    def perform_destroy(self, instance):
        _require_class_teacher_or_academic_lead(self.request.user, instance.school_class_id)
        instance.delete()


def _academic_student_scope(queryset, user):
    if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS):
        return queryset
    teacher = getattr(user, "teacher_profile", None)
    if teacher:
        return queryset.filter(
            models.Q(student__school_class__class_teacher=teacher)
            | models.Q(student__school_class__subject_assignments__teacher_assignments__teacher=teacher)
        ).distinct()
    return queryset.none()


def _require_class_teacher_or_academic_lead(user, school_class_id):
    if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS):
        return
    teacher = getattr(user, "teacher_profile", None)
    if teacher and teacher.class_teacher_of.filter(pk=school_class_id).exists():
        return
    raise PermissionDenied("Only the class teacher or academic leadership may change this record.")
