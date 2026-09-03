from django.conf import settings
from django.db import models


class TeacherStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    ABSENT = "Absent", "Absent"
    LATE = "Late", "Late"


class EmploymentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    TERMINATED = "Terminated", "Terminated"
    ON_LEAVE = "On Leave", "On Leave"


class StaffType(models.TextChoices):
    TEACHING = "Teaching", "Teaching"
    NON_TEACHING = "Non-Teaching", "Non-Teaching"


class RecruitmentStatus(models.TextChoices):
    PENDING = "Pending", "Pending"
    HIRED = "Hired", "Hired"
    REJECTED = "Rejected", "Rejected"


class Teacher(models.Model):
    """
    Name/email live on `user` (the OneToOne'd accounts.User), not duplicated
    here. `subjects`/`classes`/`subjectPapers` from the frontend's Teacher
    type are NOT stored here either — apps.academics.TeacherAssignment is
    the single canonical source of "who teaches what where" (matching the
    frontend's own "single source of truth" comment on SchoolClass); storing
    a second informational copy here would just let the two drift.
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="teacher_profile")
    attendance = models.FloatField(default=100, help_text="Attendance rate, percent")
    performance = models.FloatField(default=0, help_text="Performance score, percent")
    phone = models.CharField(max_length=30)
    status = models.CharField(max_length=10, choices=TeacherStatus.choices, default=TeacherStatus.ACTIVE)
    join_date = models.DateField()

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class NonTeachingStaff(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="non_teaching_profile")
    # Free-text job title (e.g. "Bursar", "Secretary", "Security Guard",
    # "Cook") — distinct from accounts.Role, which only tracks broad login
    # permissions, not the person's actual job title.
    job_title = models.CharField(max_length=100)
    department = models.CharField(max_length=100)
    phone = models.CharField(max_length=30)
    join_date = models.DateField()
    status = models.CharField(max_length=15, choices=EmploymentStatus.choices, default=EmploymentStatus.ACTIVE)

    class Meta:
        verbose_name_plural = "non-teaching staff"

    def __str__(self):
        return self.user.get_full_name() or self.user.username


class RecruitmentRecord(models.Model):
    candidate_name = models.CharField(max_length=200)
    staff_type = models.CharField(max_length=15, choices=StaffType.choices)
    role = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30)
    applied_date = models.DateField()
    status = models.CharField(max_length=10, choices=RecruitmentStatus.choices, default=RecruitmentStatus.PENDING)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.candidate_name} ({self.role})"


class BiometricLog(models.Model):
    """Staff attendance sign-in/out. `staff` FKs straight to User — every
    staff member has a real account now, so staff_type is just
    `staff.role`, no need for a polymorphic (id, type) pair."""

    staff = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="biometric_logs")
    date = models.DateField()
    sign_in = models.TimeField(null=True, blank=True)
    sign_out = models.TimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        unique_together = [("staff", "date")]

    def __str__(self):
        return f"{self.staff} — {self.date}"

    @property
    def hours(self) -> float:
        """
        Port of the frontend's computeHours(): 0 if either mark is missing,
        else the raw (out - in) difference in hours, clamped to >=0. No
        overnight/midnight-wrap handling — a sign-out before sign-in just
        clamps to 0, matching the original behavior exactly (not a bug fix).
        """
        if not self.sign_in or not self.sign_out:
            return 0.0
        in_minutes = self.sign_in.hour * 60 + self.sign_in.minute
        out_minutes = self.sign_out.hour * 60 + self.sign_out.minute
        return max(0.0, (out_minutes - in_minutes) / 60)
