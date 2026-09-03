from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import IsDOSOrAdmin, IsHeadmasterOrAdmin
from apps.staff.models import Teacher

from .models import ClassSubjectAssignment, Department, ReportCardConfig, ResultWindow, SchoolClass, Subject, SubjectPaper
from .serializers import (
    AssignTeacherSerializer,
    ClassSubjectAssignmentSerializer,
    DepartmentSerializer,
    ReportCardConfigSerializer,
    RemoveTeacherSerializer,
    ResultWindowSerializer,
    SchoolClassSerializer,
    SubjectPaperSerializer,
    SubjectSerializer,
)
from .services import assign_teacher_to_class_subject, remove_teacher_from_class_subject


class ReadAllWriteDOSOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return IsDOSOrAdmin().has_permission(request, view)


class ReadAllWriteHeadmasterOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return IsHeadmasterOrAdmin().has_permission(request, view)


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.prefetch_related("papers").all()
    serializer_class = SubjectSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["level", "status"]


class SubjectPaperViewSet(viewsets.ModelViewSet):
    queryset = SubjectPaper.objects.all()
    serializer_class = SubjectPaperSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["subject"]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.prefetch_related("subjects").select_related("head_teacher__user").all()
    serializer_class = DepartmentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]


class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset = SchoolClass.objects.select_related("class_teacher__user").prefetch_related(
        "subject_assignments__subject", "subject_assignments__teacher_assignments__teacher__user"
    )
    serializer_class = SchoolClassSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["level", "level_group"]

    @action(detail=True, methods=["post"], url_path="assign-teacher")
    def assign_teacher(self, request, pk=None):
        """POST .../classes/{id}/assign-teacher/ — port of
        assignTeacherToClassSubject(): merges papers idempotently if this
        teacher already has an assignment for the subject."""
        school_class = self.get_object()
        serializer = AssignTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject = Subject.objects.get(pk=data["subject_id"])
        teacher = Teacher.objects.get(pk=data["teacher_id"])
        ta = assign_teacher_to_class_subject(
            school_class, subject, teacher, data["papers"], data["assignment_type"]
        )
        return Response({"id": ta.id, "papers": ta.papers}, status=200)

    @action(detail=True, methods=["post"], url_path="remove-teacher")
    def remove_teacher(self, request, pk=None):
        """POST .../classes/{id}/remove-teacher/ — port of
        removeTeacherFromClassSubject(): removes ALL of this teacher's
        papers for the subject in one call."""
        school_class = self.get_object()
        serializer = RemoveTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        subject = Subject.objects.get(pk=data["subject_id"])
        teacher = Teacher.objects.get(pk=data["teacher_id"])
        remove_teacher_from_class_subject(school_class, subject, teacher)
        return Response(status=204)


class ClassSubjectAssignmentViewSet(viewsets.ModelViewSet):
    queryset = ClassSubjectAssignment.objects.select_related("school_class", "subject")
    serializer_class = ClassSubjectAssignmentSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["school_class", "subject"]


class ReportCardConfigViewSet(viewsets.ModelViewSet):
    """HM-managed: which assessment categories count toward report cards."""

    queryset = ReportCardConfig.objects.all()
    serializer_class = ReportCardConfigSerializer
    permission_classes = [ReadAllWriteHeadmasterOrAdmin]
    filterset_fields = ["term", "year"]


class ResultWindowViewSet(viewsets.ModelViewSet):
    """DOS-managed: submission windows per result category/term/year."""

    queryset = ResultWindow.objects.all()
    serializer_class = ResultWindowSerializer
    permission_classes = [ReadAllWriteDOSOrAdmin]
    filterset_fields = ["result_type", "term", "year"]
