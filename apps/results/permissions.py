"""
Scope-based permissions that need staff/academics models — kept separate
from apps.accounts.permissions (base role-only checks) per plan doc §Phase 7.
"""

from rest_framework.permissions import BasePermission

from apps.accounts.models import Role


class IsDOSOrAdmin(BasePermission):
    # Headmaster included alongside Admin — see apps.accounts.permissions.HasRole's
    # docstring: Admin/Headmaster are equivalent "full system access" roles.
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or user.role in (Role.DOS, Role.ADMIN, Role.HEADMASTER)))


class IsSubmittingTeacherOfScope(BasePermission):
    """The request.user must be the Teacher who owns the TeacherAssignment
    for this upload's (school_class, subject) — i.e. they're actually
    assigned to teach it, matching the frontend's implicit assumption that
    a teacher only ever submits for their own classes."""

    def has_object_permission(self, request, view, upload):
        teacher = getattr(request.user, "teacher_profile", None)
        if not teacher:
            return False
        if upload.teacher_id != teacher.id:
            return False
        return upload.school_class.subject_assignments.filter(
            subject_id=upload.subject_id, teacher_assignments__teacher=teacher
        ).exists()


class IsClassTeacherOfScope(BasePermission):
    """The request.user must be the Teacher who is SchoolClass.class_teacher
    for this upload's class."""

    def has_object_permission(self, request, view, upload):
        teacher = getattr(request.user, "teacher_profile", None)
        if not teacher:
            return False
        return upload.school_class.class_teacher_id == teacher.id
