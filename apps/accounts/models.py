from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = "ADMIN", "Administrator"
    HEADMASTER = "HEADMASTER", "Head Master"
    DOS = "DOS", "Director of Studies"
    BURSAR = "BURSAR", "Bursar"
    HR = "HR", "Human Resources"
    TEACHER = "TEACHER", "Teacher"
    NON_TEACHING = "NON_TEACHING", "Non-Teaching Staff"


class User(AbstractUser):
    """
    Custom user model. Every human who can log in — teachers, non-teaching
    staff, and admin-side roles (Admin/HM/DOS/Bursar/HR) — is a User with a
    role. Teacher- and NonTeachingStaff-specific fields live on their own
    profile models in apps.staff, linked back here via a OneToOne.

    Unlike the frontend prototype (which has no real admin auth at all, and
    a teacher "login" that never checks a password — see plan doc), every
    role here goes through real Django auth + JWT.
    """

    role = models.CharField(max_length=20, choices=Role.choices)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"
