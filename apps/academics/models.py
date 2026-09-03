from django.db import models

from apps.core.models import FinanceTerm, ResultType


class EducationLevel(models.TextChoices):
    O_LEVEL = "O-Level", "O-Level"
    A_LEVEL = "A-Level", "A-Level"


class SubjectLevel(models.TextChoices):
    O_LEVEL = "O-Level", "O-Level"
    A_LEVEL = "A-Level", "A-Level"
    BOTH = "Both", "Both"


class SubjectTypeForLevel(models.TextChoices):
    COMPULSORY = "Compulsory", "Compulsory"
    OPTIONAL = "Optional", "Optional"
    NOT_APPLICABLE = "N/A", "N/A"


class SubjectStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    INACTIVE = "Inactive", "Inactive"


class LevelGroup(models.TextChoices):
    SENIOR_1 = "Senior 1", "Senior 1"
    SENIOR_2 = "Senior 2", "Senior 2"
    SENIOR_3 = "Senior 3", "Senior 3"
    SENIOR_4 = "Senior 4", "Senior 4"
    SENIOR_5 = "Senior 5", "Senior 5"
    SENIOR_6 = "Senior 6", "Senior 6"


class AssignmentType(models.TextChoices):
    """
    Normalized to Compulsory/Optional — the vocabulary already used by
    Subject.o_level_type/a_level_type and StudentSubjectEnrollment.type. The
    frontend's ClassSubjectAssignment used "Elective" instead of "Optional"
    for the same concept; that was the one outlier, so it's fixed here
    rather than replicated.
    """

    COMPULSORY = "Compulsory", "Compulsory"
    OPTIONAL = "Optional", "Optional"


class Subject(models.Model):
    """
    `teachers`/`classes` string-list fields from the frontend's Subject type
    are intentionally NOT stored here — TeacherAssignment (below) is the
    single canonical source of who teaches what where, same reasoning as
    dropping those fields from staff.Teacher. The frontend's generic `type`
    field (separate from o_level_type/a_level_type) was itself flagged as a
    legacy/unused duplicate and is dropped rather than ported.
    """

    subject_code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100, unique=True)
    o_level_type = models.CharField(max_length=10, choices=SubjectTypeForLevel.choices)
    a_level_type = models.CharField(max_length=10, choices=SubjectTypeForLevel.choices)
    level = models.CharField(max_length=10, choices=SubjectLevel.choices)
    status = models.CharField(max_length=10, choices=SubjectStatus.choices, default=SubjectStatus.ACTIVE)
    students_enrolled = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    def type_for_level(self, level: str) -> str:
        """Port of getSubjectTypeForLevel()."""
        return self.o_level_type if level == EducationLevel.O_LEVEL else self.a_level_type


class SubjectPaper(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="papers")
    paper = models.CharField(max_length=20)
    label = models.CharField(max_length=150)

    class Meta:
        unique_together = [("subject", "paper")]
        ordering = ["paper"]

    def __str__(self):
        return f"{self.subject.name} — {self.paper}"


class Department(models.Model):
    name = models.CharField(max_length=150, unique=True)
    subjects = models.ManyToManyField(Subject, related_name="departments", blank=True)
    head_teacher = models.ForeignKey(
        "staff.Teacher", null=True, blank=True, on_delete=models.SET_NULL, related_name="headed_departments"
    )

    def __str__(self):
        return self.name


class SchoolClass(models.Model):
    """
    A real, timetabled class/stream (e.g. "Senior 2 A") — the frontend's
    comment that streams are "real classes, not derived concepts" is
    load-bearing: level_group is a rollup label for reporting only, never a
    row a student is actually enrolled in.
    """

    name = models.CharField(max_length=100, unique=True)
    level_group = models.CharField(max_length=10, choices=LevelGroup.choices)
    stream = models.CharField(max_length=20, help_text='e.g. "A"/"B" (O-Level) or "Science"/"Arts" (A-Level)')
    level = models.CharField(max_length=10, choices=EducationLevel.choices)
    class_teacher = models.ForeignKey(
        "staff.Teacher", null=True, blank=True, on_delete=models.SET_NULL, related_name="class_teacher_of"
    )

    class Meta:
        verbose_name_plural = "school classes"
        ordering = ["level_group", "stream"]

    def __str__(self):
        return self.name


class ClassSubjectAssignment(models.Model):
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE, related_name="subject_assignments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="class_assignments")
    type = models.CharField(max_length=10, choices=AssignmentType.choices)

    class Meta:
        unique_together = [("school_class", "subject")]

    def __str__(self):
        return f"{self.school_class.name} — {self.subject.name} ({self.type})"


class TeacherAssignment(models.Model):
    """Who teaches this class+subject, and which papers. `papers` is a
    small JSON list of paper labels (e.g. ["Paper 1", "Paper 2"]) — no
    separate child table, papers are already normalized once via
    SubjectPaper and this is just which of them this teacher covers."""

    class_subject_assignment = models.ForeignKey(
        ClassSubjectAssignment, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    teacher = models.ForeignKey("staff.Teacher", on_delete=models.CASCADE, related_name="teaching_assignments")
    papers = models.JSONField(default=list, blank=True)

    class Meta:
        unique_together = [("class_subject_assignment", "teacher")]

    def __str__(self):
        return f"{self.teacher} — {self.class_subject_assignment}"


class ReportCardConfig(models.Model):
    """
    HM-managed: which assessment categories count toward report cards for a
    given term/year. No row for a term/year means "everything counts" —
    that fallback is implemented in results/services.py
    (get_included_result_types), not here.
    """

    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    included_result_types = models.JSONField(default=list)

    class Meta:
        unique_together = [("term", "year")]

    def __str__(self):
        return f"ReportCardConfig {self.term} {self.year}"


class ResultWindow(models.Model):
    """DOS-managed submission window for one result category/term/year."""

    result_type = models.CharField(max_length=20, choices=ResultType.choices)
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()

    def __str__(self):
        return f"{self.result_type} — {self.term} {self.year}"
