from django.db import models

from apps.academics.models import AssignmentType, EducationLevel, SchoolClass, Subject, SubjectPaper
from apps.core.models import FinanceTerm


class Gender(models.TextChoices):
    MALE = "Male", "Male"
    FEMALE = "Female", "Female"


class EnrollmentStatus(models.TextChoices):
    ENROLLED = "Enrolled", "Enrolled"
    PENDING = "Pending", "Pending"


class SubjectEnrollmentStatus(models.TextChoices):
    ACTIVE = "Active", "Active"
    DROPPED = "Dropped", "Dropped"
    PENDING = "Pending", "Pending"


class AttendanceMark(models.TextChoices):
    PRESENT = "P", "Present"
    ABSENT = "A", "Absent"


class Student(models.Model):
    """
    `level` is intentionally NOT a stored field — the frontend keeps it as a
    flat copy of the student's class's level, always kept in sync by
    construction (a student's level only ever changes by changing class);
    storing it separately here would just be a second copy that could drift.
    Use the `level` property below, or `school_class__level` in querysets.
    """

    student_number = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=200)
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT, related_name="students")
    combination = models.CharField(max_length=30, blank=True, help_text="A-Level only, e.g. PCM/ICT")
    performance = models.FloatField(default=0, help_text="Cached latest-term average; kept in sync by the results engine")
    email = models.EmailField(blank=True)
    gender = models.CharField(max_length=10, choices=Gender.choices)
    age = models.PositiveIntegerField(null=True, blank=True)
    religion = models.CharField(max_length=50, blank=True)
    location = models.CharField(max_length=150, blank=True)
    enrollment_date = models.DateField()
    photo_url = models.URLField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.student_number})"

    @property
    def level(self) -> str:
        return self.school_class.level


class ParentInfo(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, related_name="parent_info")
    father_name = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    guardian = models.CharField(max_length=200, blank=True)
    phone = models.CharField(max_length=30)
    alt_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    location = models.CharField(max_length=150)
    district = models.CharField(max_length=100)

    def __str__(self):
        return f"Parents of {self.student.name}"


class StudentSubjectEnrollment(models.Model):
    """Replaces the frontend's embedded Student.subjects[]. This is the
    LIVE current-term paper score, upserted by the results engine on
    confirm — see apps.results.services.apply_result_upload."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="subject_enrollments")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    paper = models.ForeignKey(SubjectPaper, null=True, blank=True, on_delete=models.CASCADE)
    type = models.CharField(max_length=10, choices=AssignmentType.choices)
    status = models.CharField(max_length=10, choices=SubjectEnrollmentStatus.choices, default=SubjectEnrollmentStatus.ACTIVE)
    score = models.FloatField(null=True, blank=True)
    grade = models.CharField(max_length=1, blank=True)

    class Meta:
        # NULL `paper` isn't caught by this constraint on MySQL (NULL != NULL
        # in a unique index), so two paperless rows for the same
        # student+subject are technically possible at the DB level. The
        # results engine's upsert logic never creates a duplicate in
        # practice (it always looks up by subject+paper first), so this is
        # a documented gap, not something worth a sentinel-value workaround.
        unique_together = [("student", "subject", "paper")]

    def __str__(self):
        return f"{self.student.name} — {self.subject.name} {self.paper or ''}".strip()


class TermEnrollment(models.Model):
    """
    Which class a student was actually in during a given term — a
    historical snapshot, since promotion/stream changes happen between
    terms. `school_class` is FK'd (not a frozen name string) because the 12
    SchoolClass rows are permanent timetable slots, not per-cohort
    instances — see plan doc §2a.
    """

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="term_enrollments")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.PROTECT)
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    level = models.CharField(max_length=10, choices=EducationLevel.choices)
    combination = models.CharField(max_length=30, blank=True)
    enrollment_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=EnrollmentStatus.choices)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("student", "term", "year")]

    def __str__(self):
        return f"{self.student.name} — {self.term} {self.year} ({self.status})"


class TermRecord(models.Model):
    """
    One student's summary for one term: rank/average, plus the three
    MANUAL-OVERRIDE comment fields (falls back to a live-generated comment
    when unset — see apps.results.services.generate_role_comment). Confirmed
    zero seed rows have these set; every comment shown today is generated.
    """

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="term_records")
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    class_position = models.PositiveIntegerField(null=True, blank=True)
    total_students = models.PositiveIntegerField(null=True, blank=True)
    average = models.FloatField(null=True, blank=True)
    class_teacher_comment = models.TextField(blank=True)
    dos_comment = models.TextField(blank=True)
    hm_comment = models.TextField(blank=True)

    class Meta:
        unique_together = [("student", "term", "year")]

    def __str__(self):
        return f"{self.student.name} — {self.term} {self.year}"


class TermSubjectMark(models.Model):
    """Replaces the frontend's embedded TermRecord.marks[]. Always
    subject-level, never paper-level — applyResultUpload only ever upserts
    these keyed by subject name, so there's no paper field here even though
    the frontend's TermRecord.marks[] interface technically allowed one."""

    term_record = models.ForeignKey(TermRecord, on_delete=models.CASCADE, related_name="marks")
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    score = models.FloatField()
    grade = models.CharField(max_length=1)

    class Meta:
        unique_together = [("term_record", "subject")]

    def __str__(self):
        return f"{self.term_record} — {self.subject.name}: {self.score}"


class StudentAttendanceRecord(models.Model):
    """Normalizes the frontend's embedded StudentAttendanceRecord.marks[]
    into one row per student per day."""

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="attendance_records")
    school_class = models.ForeignKey(SchoolClass, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=1, choices=AttendanceMark.choices)

    class Meta:
        unique_together = [("student", "date")]
        ordering = ["-date"]

    def __str__(self):
        return f"{self.student.name} — {self.date} ({self.status})"
