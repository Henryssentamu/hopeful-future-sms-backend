from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Role
from apps.accounts.permissions import IsHROrAdmin

from .models import BiometricLog, NonTeachingStaff, RecruitmentRecord, Teacher
from .serializers import (
    BiometricLogSerializer,
    NonTeachingStaffSerializer,
    RecruitmentRecordSerializer,
    TeacherSerializer,
    TeacherDirectorySerializer,
)
from .services import CandidateNotHireable, hire_candidate, reset_password


class ReadAllWriteHROrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            user = request.user
            return bool(user and user.is_authenticated and (
                user.is_superuser or user.role in (
                    Role.ADMIN, Role.HEADMASTER, Role.HR, Role.DOS, Role.TEACHER, Role.NON_TEACHING,
                )
            ))
        return IsHROrAdmin().has_permission(request, view)


class TeacherViewSet(viewsets.ModelViewSet):
    queryset = Teacher.objects.select_related("user").all()
    serializer_class = TeacherSerializer
    permission_classes = [ReadAllWriteHROrAdmin]
    filterset_fields = ["status"]

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.HR, Role.DOS):
            return qs
        teacher = getattr(user, "teacher_profile", None)
        return qs.filter(pk=teacher.pk) if teacher else qs.none()

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated])
    def directory(self, request):
        """Minimal teacher identity map for result-review notifications and assignment labels."""
        teachers = Teacher.objects.select_related("user").filter(user__is_active=True)
        return Response(TeacherDirectorySerializer(teachers, many=True).data)

    @action(detail=True, methods=["get"])
    def roles(self, request, pk=None):
        """GET /api/staff/teachers/{id}/roles/ — port of getTeacherRoles():
        derived from SchoolClass.class_teacher / Department.head_teacher,
        not a stored field."""
        from apps.academics.services import get_teacher_roles

        teacher = self.get_object()
        return Response(get_teacher_roles(teacher))

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password_action(self, request, pk=None):
        """POST /api/staff/teachers/{id}/reset-password/ — Admin/Headmaster/HR
        only (see ReadAllWriteHROrAdmin above). Generates and returns a new
        one-time password for this teacher's login."""
        teacher = self.get_object()
        new_password = reset_password(teacher.user)
        return Response({"username": teacher.user.username, "generated_password": new_password})


class NonTeachingStaffViewSet(viewsets.ModelViewSet):
    queryset = NonTeachingStaff.objects.select_related("user").all()
    serializer_class = NonTeachingStaffSerializer
    permission_classes = [ReadAllWriteHROrAdmin]
    filterset_fields = ["status", "department"]

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.HR):
            return qs
        profile = getattr(user, "non_teaching_profile", None)
        return qs.filter(pk=profile.pk) if profile else qs.none()

    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password_action(self, request, pk=None):
        """POST /api/staff/non-teaching/{id}/reset-password/ — same as
        TeacherViewSet's action, for non-teaching staff."""
        staff = self.get_object()
        new_password = reset_password(staff.user)
        return Response({"username": staff.user.username, "generated_password": new_password})


class RecruitmentRecordViewSet(viewsets.ModelViewSet):
    queryset = RecruitmentRecord.objects.all()
    serializer_class = RecruitmentRecordSerializer
    permission_classes = [IsHROrAdmin]
    filterset_fields = ["status", "staff_type"]

    @action(detail=True, methods=["post"])
    def hire(self, request, pk=None):
        """POST /api/staff/recruitment/{id}/hire/ — materializes a Teacher
        or NonTeachingStaff (+ User account) from this candidate and marks
        the record Hired. Port of StaffContext.hireCandidate."""
        try:
            result = hire_candidate(int(pk))
        except CandidateNotHireable as exc:
            return Response({"detail": str(exc)}, status=409)
        if result is None:
            return Response({"detail": "Candidate not found."}, status=404)
        if isinstance(result.profile, Teacher):
            profile_data = TeacherSerializer(result.profile).data
        else:
            profile_data = NonTeachingStaffSerializer(result.profile).data
        return Response(
            {
                "profile": profile_data,
                "username": result.user.username,
                "generated_password": result.generated_password,
            },
            status=201,
        )


class BiometricLogViewSet(viewsets.ModelViewSet):
    queryset = BiometricLog.objects.select_related("staff").all()
    serializer_class = BiometricLogSerializer
    permission_classes = [IsHROrAdmin]
    filterset_fields = ["staff", "date"]
