from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError

from apps.accounts.models import Role
from apps.staff.models import Teacher

from .models import ClassSubjectAssignment, Department, ReportCardConfig, ResultWindow, SchoolClass, Subject, SubjectPaper
from .serializers import (
    AssignTeacherSerializer,
    ClassSubjectAssignmentSerializer,
    DepartmentSerializer,
    ReportCardConfigSerializer,
    RemoveTeacherSerializer,
    ReassignClassTeacherSerializer,
    ResultWindowSerializer,
    SchoolClassSerializer,
    SubjectPaperSerializer,
    SubjectSerializer,
)
from .services import assign_teacher_to_class_subject, reassign_class_teacher, remove_teacher_from_class_subject


class AcademicRolePermission(permissions.BasePermission):
    """Apply the explicit read/write role sets declared by an academic view."""

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        allowed_roles = view.read_roles if request.method in permissions.SAFE_METHODS else view.write_roles
        return user.role in allowed_roles


class SchoolClassPermission(AcademicRolePermission):
    """HR may assign a class teacher without gaining general academic mutation rights."""

    def has_permission(self, request, view):
        if super().has_permission(request, view):
            return True
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role == Role.HR
            and (
                (view.action == "partial_update" and set(request.data) <= {"class_teacher"})
                or view.action == "reassign_class_teacher"
            )
        )


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.prefetch_related("papers").order_by("name", "id")
    serializer_class = SubjectSerializer
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.HR, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS)
    filterset_fields = ["level", "status", "category"]

    @action(detail=False, methods=["post"], url_path="load-advanced-catalogue")
    def load_advanced_catalogue(self, request):
        from .catalogue import load_advanced_subjects
        try:
            load_advanced_subjects()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        return Response({"detail": "NCDC A-Level subject menu loaded."})

    @action(detail=False, methods=["post"], url_path="load-ordinary-catalogue")
    def load_ordinary_catalogue(self, request):
        from .catalogue import load_ordinary_subjects
        try:
            load_ordinary_subjects()
        except ValueError as error:
            raise ValidationError(str(error)) from error
        return Response({"detail": "NCDC O-Level subject menu loaded."})


class SubjectPaperViewSet(viewsets.ModelViewSet):
    queryset = SubjectPaper.objects.all()
    serializer_class = SubjectPaperSerializer
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.HR, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS)
    filterset_fields = ["subject"]


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.prefetch_related("subjects").select_related("head_teacher__user").all()
    serializer_class = DepartmentSerializer
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.HR, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.HR)


class SchoolClassViewSet(viewsets.ModelViewSet):
    queryset = SchoolClass.objects.select_related("class_teacher__user").prefetch_related(
        "subject_assignments__subject", "subject_assignments__teacher_assignments__teacher__user"
    )
    serializer_class = SchoolClassSerializer
    permission_classes = [SchoolClassPermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.HR, Role.BURSAR, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS)
    filterset_fields = ["level", "level_group"]

    @action(detail=True, methods=["post"], url_path="reassign-class-teacher")
    def reassign_class_teacher(self, request, pk=None):
        target_class = self.get_object()
        serializer = ReassignClassTeacherSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        teacher = get_object_or_404(Teacher, pk=serializer.validated_data["teacher_id"])
        updated_class = reassign_class_teacher(target_class, teacher)
        return Response(self.get_serializer(updated_class).data, status=200)

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
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS)
    filterset_fields = ["school_class", "subject"]


class ReportCardConfigViewSet(viewsets.ModelViewSet):
    """HM-managed: which assessment categories count toward report cards."""

    queryset = ReportCardConfig.objects.order_by("-year", "term", "id")
    serializer_class = ReportCardConfigSerializer
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER)
    filterset_fields = ["term", "year"]


class ResultWindowViewSet(viewsets.ModelViewSet):
    """DOS-managed: submission windows per result category/term/year."""

    queryset = ResultWindow.objects.order_by("-year", "term", "result_type", "id")
    serializer_class = ResultWindowSerializer
    permission_classes = [AcademicRolePermission]
    read_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.TEACHER)
    write_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS)
    filterset_fields = ["result_type", "term", "year"]
