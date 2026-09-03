from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsDOSOrAdmin, IsHeadmasterOrAdmin

from .models import ParentInfo, Student, StudentAttendanceRecord, StudentSubjectEnrollment, TermEnrollment, TermRecord
from .serializers import (
    ParentInfoSerializer,
    StudentAttendanceRecordSerializer,
    StudentSerializer,
    StudentSubjectEnrollmentSerializer,
    TermEnrollmentSerializer,
    TermRecordSerializer,
    UpdateCommentSerializer,
)


class ReadAllWriteDOSOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return IsDOSOrAdmin().has_permission(request, view)


class ReadAllWriteAdminSide(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role in (
            Role.ADMIN, Role.DOS, Role.HEADMASTER, Role.TEACHER,
        )))


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
            enrollment = TermEnrollment.objects.filter(student=student, term=term, year=year).select_related(
                "school_class__class_teacher__user"
            ).first()
            class_teacher = enrollment.school_class.class_teacher if enrollment else student.school_class.class_teacher
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


class StudentSubjectEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = StudentSubjectEnrollment.objects.select_related("student", "subject", "paper")
    serializer_class = StudentSubjectEnrollmentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student", "subject", "status"]


class TermEnrollmentViewSet(viewsets.ModelViewSet):
    queryset = TermEnrollment.objects.select_related("student", "school_class")
    serializer_class = TermEnrollmentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student", "term", "year", "status"]


class TermRecordViewSet(viewsets.ModelViewSet):
    queryset = TermRecord.objects.select_related("student").prefetch_related("marks__subject")
    serializer_class = TermRecordSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["student", "term", "year"]


class StudentAttendanceRecordViewSet(viewsets.ModelViewSet):
    queryset = StudentAttendanceRecord.objects.select_related("student", "school_class")
    serializer_class = StudentAttendanceRecordSerializer
    permission_classes = [ReadAllWriteAdminSide]
    filterset_fields = ["student", "school_class", "date"]
