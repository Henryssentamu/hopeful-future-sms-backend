from django.conf import settings
from django.db import models


class FinanceTerm(models.TextChoices):
    """
    Matches the frontend's FinanceTerm union exactly ("Term 1"|"Term 2"|
    "Term 3") — used everywhere a term needs to be stored/compared, not just
    in finance models.
    """

    TERM_1 = "Term 1", "Term 1"
    TERM_2 = "Term 2", "Term 2"
    TERM_3 = "Term 3", "Term 3"


class ResultType(models.TextChoices):
    """Matches the frontend's ResultType union exactly."""

    BEGINNING_OF_TERM = "Beginning of Term", "Beginning of Term"
    TEST = "Test", "Test"
    MIDTERM = "Midterm", "Midterm"
    PROJECT = "Project", "Project"
    END_OF_TERM = "End of Term", "End of Term"


class SingletonModel(models.Model):
    """
    Base for models that only ever have one row (SchoolInfo, AcademicPeriod).
    Always saves to pk=1; `load()` returns the row, creating it with the
    model's field defaults the first time it's called.
    """

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class SchoolInfo(SingletonModel):
    """Replaces the frontend's SCHOOL_INFO constant."""

    name = models.CharField(max_length=255, default="HOPEFUL FUTURE SECONDARY SCHOOL")
    short_name = models.CharField(max_length=100, default="Hopeful Future SS")
    location = models.CharField(max_length=255, default="Kayunga - Ntooke")
    po_box = models.CharField(max_length=100, default="P.O. Box 18174, Kayunga")
    phone = models.CharField(max_length=50, default="0704943539")
    email = models.EmailField(default="hopefulfuturesecschool@gmail.com")
    motto = models.CharField(max_length=255, default="Our Hope Has Strong Wings")

    def __str__(self):
        return self.name


class AcademicPeriod(SingletonModel):
    """
    The real, server-side "active term/year" — replaces the frontend's
    AcademicPeriodContext, which only ever persisted this to the browser's
    localStorage (i.e. every visitor could have a different idea of what
    the active period was). Admin-only to change.
    """

    active_term = models.CharField(max_length=10, choices=FinanceTerm.choices, default=FinanceTerm.TERM_1)
    active_year = models.PositiveIntegerField(default=2025)

    def __str__(self):
        return f"{self.active_term} {self.active_year}"


class ActivityType(models.TextChoices):
    INFO = "info", "Info"
    SUCCESS = "success", "Success"
    WARNING = "warning", "Warning"


class Activity(models.Model):
    """Dashboard/audit activity feed — replaces the frontend's recentActivities."""

    message = models.CharField(max_length=500)
    type = models.CharField(max_length=10, choices=ActivityType.choices, default=ActivityType.INFO)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "activities"

    def __str__(self):
        return self.message
