"""
Base, role-only permission classes. Scope-based permissions that need to
check a specific SchoolClass/TeacherAssignment (e.g. "is this user the class
teacher of THIS class") live in apps.results.permissions instead, since they
depend on apps.staff/apps.academics models — see plan doc, Phase 7.
"""

from rest_framework.permissions import BasePermission

from .models import Role


class HasRole(BasePermission):
    """Base class — subclass and set `allowed_roles`.

    Admin and Headmaster are equivalent "full system access" roles
    throughout this app (the frontend's RoleGuard gives both — and only
    both — the sidebar and every route); any permission class that lists
    Role.ADMIN therefore implicitly also allows Role.HEADMASTER, so a
    Headmaster is never blocked from something an Admin can do.
    """

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser:
            return True
        effective_roles = self.allowed_roles
        if Role.ADMIN in effective_roles and Role.HEADMASTER not in effective_roles:
            effective_roles = effective_roles + (Role.HEADMASTER,)
        return user.role in effective_roles


class IsAdmin(HasRole):
    allowed_roles = (Role.ADMIN,)


class IsHeadmaster(HasRole):
    allowed_roles = (Role.HEADMASTER,)


class IsDOS(HasRole):
    allowed_roles = (Role.DOS,)


class IsDOSOrAdmin(HasRole):
    allowed_roles = (Role.DOS, Role.ADMIN)


class IsHeadmasterOrAdmin(HasRole):
    allowed_roles = (Role.HEADMASTER, Role.ADMIN)


class IsBursarOrAdmin(HasRole):
    allowed_roles = (Role.BURSAR, Role.ADMIN)


class IsHROrAdmin(HasRole):
    allowed_roles = (Role.HR, Role.ADMIN)


class IsTeacher(HasRole):
    allowed_roles = (Role.TEACHER,)


class IsAdminSideStaff(HasRole):
    """Any of the admin-facing roles (everyone except Teacher/Non-Teaching)."""

    allowed_roles = (Role.ADMIN, Role.HEADMASTER, Role.DOS, Role.BURSAR, Role.HR)
