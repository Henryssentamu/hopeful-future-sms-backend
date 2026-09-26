"""
Port of StaffContext.hireCandidate (frontend). The original code comment
notes: "previously 'Hire' only flipped the status field" — it was upgraded
to actually materialize a new Teacher/NonTeachingStaff record, which is
exactly the kind of state-transition logic that belongs in a service
function + a dedicated endpoint, not plain model CRUD.

Difference from the frontend: a real account (accounts.User) has to be
created too, since Teacher/NonTeachingStaff both require one — the frontend
had no concept of login credentials for staff at all. We generate a unique
username from the candidate's email (or name, if no email) and a random
password, returned once in the API response for the admin to relay to the
new hire.
"""

import datetime
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.crypto import get_random_string
from django.utils.text import slugify

from apps.accounts.models import Role

from .models import NonTeachingStaff, RecruitmentRecord, RecruitmentStatus, StaffType, Teacher

User = get_user_model()


@dataclass
class HireResult:
    profile: Teacher | NonTeachingStaff
    user: "User"
    generated_password: str


class CandidateNotHireable(Exception):
    pass


def _unique_username(base: str) -> str:
    base = slugify(base) or "staff"
    username = base
    n = 1
    while User.objects.filter(username=username).exists():
        n += 1
        username = f"{base}{n}"
    return username


def hire_candidate(candidate_id: int) -> HireResult | None:
    with transaction.atomic():
        try:
            candidate = RecruitmentRecord.objects.select_for_update().get(pk=candidate_id)
        except RecruitmentRecord.DoesNotExist:
            return None
        if candidate.status == RecruitmentStatus.HIRED or candidate.hired_user_id:
            raise CandidateNotHireable("This candidate has already been hired.")
        if candidate.status != RecruitmentStatus.PENDING:
            raise CandidateNotHireable("Only a pending candidate can be hired.")

        first_name, _, last_name = candidate.candidate_name.partition(" ")
        username_base = candidate.email.split("@")[0] if candidate.email else candidate.candidate_name
        username = _unique_username(f"{username_base}-{candidate.pk}")
        password = get_random_string(12)

        role = Role.TEACHER if candidate.staff_type == StaffType.TEACHING else Role.NON_TEACHING
        user = User.objects.create_user(
            username=username,
            email=candidate.email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            password=password,
        )

        today = datetime.date.today()
        if candidate.staff_type == StaffType.TEACHING:
            profile = Teacher.objects.create(
                user=user,
                attendance=100,
                performance=0,
                phone=candidate.phone,
                status="Active",
                join_date=today,
            )
        else:
            profile = NonTeachingStaff.objects.create(
                user=user,
                job_title=candidate.role,
                department="General",  # hardcoded, matches the frontend exactly
                phone=candidate.phone,
                join_date=today,
                status="Active",
            )

        candidate.status = RecruitmentStatus.HIRED
        candidate.hired_user = user
        candidate.save(update_fields=["status", "hired_user"])

    return HireResult(profile=profile, user=user, generated_password=password)


def reset_password(user: "User") -> str:
    """Generates a fresh random password for `user`, sets it, and returns
    it once — same one-time-reveal pattern as hire_candidate's generated
    password. For a staff member who's forgotten their password; the
    caller (Admin/Headmaster/HR) relays it to them securely."""
    password = get_random_string(12)
    user.set_password(password)
    user.save(update_fields=["password"])
    return password
