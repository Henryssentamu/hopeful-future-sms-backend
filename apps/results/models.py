from django.db import models

from apps.academics.models import SchoolClass, Subject, SubjectPaper
from apps.core.models import FinanceTerm, ResultType
from apps.students.models import Student


class ResultUploadStatus(models.TextChoices):
    """
    The workflow state machine: Teacher submits -> PENDING_CLASS_TEACHER ->
    Class Teacher confirms -> PENDING_DOS -> DOS confirms -> CONFIRMED
    (triggers apps.results.services.apply_result_upload). Either reviewer
    can reject (REJECTED_BY_*), and a rejected upload can be resent,
    resetting status back to PENDING_CLASS_TEACHER. DOS also has a fast
    path (enter_and_confirm) that skips straight to CONFIRMED.
    """

    PENDING_CLASS_TEACHER = "PendingClassTeacher", "With Class Teacher"
    PENDING_DOS = "PendingDOS", "With DOS"
    REJECTED_BY_CLASS_TEACHER = "RejectedByClassTeacher", "Rejected by Class Teacher"
    REJECTED_BY_DOS = "RejectedByDOS", "Rejected by DOS"
    CONFIRMED = "Confirmed", "Confirmed"


class RejectedBy(models.TextChoices):
    CLASS_TEACHER = "Class Teacher", "Class Teacher"
    DOS = "DOS", "DOS"


class ResultUpload(models.Model):
    teacher = models.ForeignKey("staff.Teacher", on_delete=models.PROTECT, related_name="result_uploads")
    subject = models.ForeignKey(Subject, on_delete=models.PROTECT)
    paper = models.ForeignKey(SubjectPaper, null=True, blank=True, on_delete=models.PROTECT)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT)
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    result_type = models.CharField(max_length=20, choices=ResultType.choices)
    weight_percent = models.FloatField()
    upload_date = models.DateField(auto_now_add=True)
    status = models.CharField(max_length=25, choices=ResultUploadStatus.choices, default=ResultUploadStatus.PENDING_CLASS_TEACHER)
    rejection_reason = models.TextField(blank=True)
    rejected_by = models.CharField(max_length=15, choices=RejectedBy.choices, blank=True)
    rejected_by_name = models.CharField(max_length=200, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-upload_date", "-id"]

    def __str__(self):
        return f"{self.subject.name} {self.paper or ''} — {self.school_class.name} — {self.term} {self.year} ({self.result_type})"

    def scope_key(self) -> tuple:
        """(subject, paper, school_class, term, year) — the exact match key
        used by apply_result_upload to find every upload contributing to a
        student's score for this paper."""
        return (self.subject_id, self.paper_id, self.school_class_id, self.term, self.year)


class ResultEntry(models.Model):
    """
    Replaces the frontend's embedded ResultUpload.entries[]. Deliberately
    does NOT duplicate studentNumber/studentName (the frontend's ResultEntry
    carried both as a denormalized snapshot) — Student already has both,
    and storing a second copy here would just be one more place for them to
    drift; join through `student` instead.
    """

    upload = models.ForeignKey(ResultUpload, on_delete=models.CASCADE, related_name="entries")
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="result_entries")
    score = models.FloatField()
    grade = models.CharField(max_length=1)

    class Meta:
        unique_together = [("upload", "student")]

    def __str__(self):
        return f"{self.upload} — {self.student.name}: {self.score}"
