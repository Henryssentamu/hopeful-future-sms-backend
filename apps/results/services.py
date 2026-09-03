"""
Bit-exact port of src/lib/grading.ts. Written as pure functions operating on
plain data/ORM objects, mirroring the JS module's shape 1:1 so each piece is
unit-testable in isolation — see apps/results/tests/test_services.py.

The single riskiest piece is `seed_from()`: the JS version does a 32-bit
signed-overflow rolling hash (`h = (h*31 + charCode) | 0` per character). A
naive Python port using plain ints (which never overflow) would compute a
completely different number and thus pick different comment-bank entries
for the same (student, term, year) — see the explicit masking below.
"""

from dataclasses import dataclass, field

from django.db import transaction

from apps.academics.models import AssignmentType
from apps.core.models import ResultType
from apps.core.services import get_previous_term

# ---------------------------------------------------------------------------
# Grading scale
# ---------------------------------------------------------------------------

GRADE_POINTS = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}

RESULT_BAND_LABELS = {
    1: "Result 1 — Excellent",
    2: "Result 2 — Very Good",
    3: "Result 3 — Good",
    4: "Result 4 — Fair",
    5: "Result 5 — Needs Improvement",
}


def get_letter_grade(score: float) -> str:
    """Port of getLetterGrade(). Exact boundaries: >=80 A, >=70 B, >=60 C, >=50 D, else F."""
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


def get_grade_points(grade: str) -> int:
    """Port of getGradePoints()."""
    return GRADE_POINTS.get(grade, 0)


def get_result_band(mean_points: float) -> int:
    """Port of getResultBand(): >=4 -> 1 (best) ... <1 -> 5 (worst)."""
    if mean_points >= 4:
        return 1
    if mean_points >= 3:
        return 2
    if mean_points >= 2:
        return 3
    if mean_points >= 1:
        return 4
    return 5


def get_performance_tier(mean_score: float) -> str:
    """Port of getPerformanceTier()."""
    if mean_score >= 80:
        return "excellent"
    if mean_score >= 70:
        return "very-good"
    if mean_score >= 60:
        return "good"
    if mean_score >= 50:
        return "fair"
    return "weak"


def get_subject_remark(score: float) -> str:
    """Port of getSubjectRemark() — same cutoffs as get_performance_tier, different labels."""
    if score >= 80:
        return "Excellent"
    if score >= 70:
        return "Very Good"
    if score >= 60:
        return "Good"
    if score >= 50:
        return "Fair"
    return "Needs Improvement"


def weighted_average(entries: list[dict]) -> float:
    """
    Port of weightedAverage(). entries: [{"score": float, "weight_percent":
    float}]. 0 if total weight is 0 (avoids divide-by-zero). Rounded to 1
    decimal place.
    """
    total_weight = sum(e["weight_percent"] for e in entries)
    if total_weight == 0:
        return 0.0
    total = sum(e["score"] * e["weight_percent"] for e in entries)
    return round(total / total_weight, 1)


def get_included_result_types(configs_qs, term: str, year: int) -> list[str]:
    """
    Port of getIncludedResultTypes(): a ReportCardConfig for this (term,
    year) if one exists, else "everything counts" (ALL_RESULT_TYPES) — the
    fallback that's actually exercised today, since the seed data has zero
    ReportCardConfig rows.
    """
    config = configs_qs.filter(term=term, year=year).first()
    if config:
        return config.included_result_types
    return [c for c, _ in ResultType.choices]


# ---------------------------------------------------------------------------
# Class ranking / apply-result-upload (the DOS-confirm sync pipeline)
# ---------------------------------------------------------------------------

def recompute_class_ranking(school_class_id: int, term: str, year: int) -> None:
    """
    Port of recomputeClassRanking(): every student in this class/term/year
    who HAS a TermRecord.average gets ranked (1-indexed, highest average
    first; ties keep whatever order the DB returns them in — matching the
    frontend's non-deterministic-but-stable JS Array.sort tie behavior,
    not an intentional tiebreak rule). Students without an average that
    term are left untouched — not zeroed, not excluded from the table,
    simply never assigned a position.
    """
    from apps.students.models import TermRecord

    records = list(
        TermRecord.objects.filter(
            student__school_class_id=school_class_id, term=term, year=year, average__isnull=False
        ).order_by("-average", "id")
    )
    total = len(records)
    for position, record in enumerate(records, start=1):
        record.class_position = position
        record.total_students = total
    TermRecord.objects.bulk_update(records, ["class_position", "total_students"])


@dataclass
class ApplyResultUploadOutcome:
    updated_student_ids: list[int] = field(default_factory=list)


def apply_result_upload(upload) -> ApplyResultUploadOutcome:
    """
    Port of applyResultUpload() — the critical DOS-confirm sync. Must run
    inside (or itself open) a transaction: it upserts StudentSubjectEnrollment
    (paper-level), TermSubjectMark + TermRecord.average (subject-level),
    Student.performance, and finally re-ranks the whole class.

    `upload` must already be status=Confirmed (the caller sets that before
    calling this, matching DataContext.confirmResultUpload's ordering).
    """
    from apps.results.models import ResultEntry, ResultUpload
    from apps.students.models import StudentSubjectEnrollment, TermRecord, TermSubjectMark

    related_uploads = list(
        ResultUpload.objects.filter(
            subject_id=upload.subject_id,
            paper_id=upload.paper_id,
            school_class_id=upload.school_class_id,
            term=upload.term,
            year=upload.year,
            status="Confirmed",
        )
    )
    related_entries_by_student: dict[int, list[dict]] = {}
    for related in related_uploads:
        for entry in ResultEntry.objects.filter(upload=related):
            related_entries_by_student.setdefault(entry.student_id, []).append(
                {"score": entry.score, "weight_percent": related.weight_percent}
            )

    this_upload_student_ids = set(ResultEntry.objects.filter(upload=upload).values_list("student_id", flat=True))
    updated_student_ids = []

    with transaction.atomic():
        for student_id in this_upload_student_ids:
            contributions = related_entries_by_student.get(student_id, [])
            if not contributions:
                continue
            paper_score = weighted_average(contributions)
            paper_grade = get_letter_grade(paper_score)

            # Upsert the paper-level StudentSubjectEnrollment. If it doesn't
            # exist yet, derive its `type` from the class's actual subject
            # assignment rather than hardcoding "Compulsory" — the frontend
            # hardcodes this even for electives, a data-integrity bug we
            # deliberately do NOT replicate (see plan doc).
            enrollment = StudentSubjectEnrollment.objects.filter(
                student_id=student_id, subject_id=upload.subject_id, paper_id=upload.paper_id
            ).first()
            if enrollment:
                enrollment.score = paper_score
                enrollment.grade = paper_grade
                enrollment.save(update_fields=["score", "grade"])
            else:
                assignment_type = AssignmentType.COMPULSORY
                csa = upload.school_class.subject_assignments.filter(subject_id=upload.subject_id).first()
                if csa:
                    assignment_type = csa.type
                StudentSubjectEnrollment.objects.create(
                    student_id=student_id,
                    subject_id=upload.subject_id,
                    paper_id=upload.paper_id,
                    type=assignment_type,
                    status="Active",
                    score=paper_score,
                    grade=paper_grade,
                )

            # Subject-level score = mean of this subject's active
            # (non-Dropped) papers with a score, using the just-updated set.
            subject_scores = list(
                StudentSubjectEnrollment.objects.filter(
                    student_id=student_id, subject_id=upload.subject_id
                ).exclude(status="Dropped").exclude(score__isnull=True).values_list("score", flat=True)
            )
            subject_score = round(sum(subject_scores) / len(subject_scores), 1) if subject_scores else paper_score
            subject_grade = get_letter_grade(subject_score)

            term_record, _ = TermRecord.objects.get_or_create(
                student_id=student_id, term=upload.term, year=upload.year
            )
            mark, _ = TermSubjectMark.objects.get_or_create(
                term_record=term_record, subject_id=upload.subject_id,
                defaults={"score": subject_score, "grade": subject_grade},
            )
            if mark.score != subject_score or mark.grade != subject_grade:
                mark.score = subject_score
                mark.grade = subject_grade
                mark.save(update_fields=["score", "grade"])

            all_marks = list(TermSubjectMark.objects.filter(term_record=term_record).values_list("score", flat=True))
            term_average = round(sum(all_marks) / len(all_marks), 1) if all_marks else subject_score
            term_record.average = term_average
            term_record.save(update_fields=["average"])

            from apps.students.models import Student
            Student.objects.filter(pk=student_id).update(performance=term_average)

            updated_student_ids.append(student_id)

        recompute_class_ranking(upload.school_class_id, upload.term, upload.year)

    return ApplyResultUploadOutcome(updated_student_ids=updated_student_ids)


# ---------------------------------------------------------------------------
# Report-card computation — live, report-card-scoped view (independent of
# the stored subjects/academicHistory, which always blend every confirmed
# category regardless of the HM's ReportCardConfig selection).
# ---------------------------------------------------------------------------

@dataclass
class ReportCardMark:
    subject_id: int
    subject_name: str
    score: float
    grade: str


def compute_report_card_marks(student_id: int, school_class_id: int, term: str, year: int, included_result_types: list[str]) -> list[ReportCardMark]:
    """Port of computeReportCardMarks()."""
    from apps.results.models import ResultEntry, ResultUpload

    relevant = (
        ResultUpload.objects.filter(
            school_class_id=school_class_id, term=term, year=year, status="Confirmed",
            result_type__in=included_result_types,
        )
        .filter(entries__student_id=student_id)
        .select_related("subject")
        .prefetch_related("entries")
    )

    # group by (subject_id, paper_id)
    paper_groups: dict[tuple, dict] = {}
    for upload in relevant:
        entry = next((e for e in upload.entries.all() if e.student_id == student_id), None)
        if not entry:
            continue
        key = (upload.subject_id, upload.paper_id)
        paper_groups.setdefault(key, {"subject_id": upload.subject_id, "subject_name": upload.subject.name, "contributions": []})
        paper_groups[key]["contributions"].append({"score": entry.score, "weight_percent": upload.weight_percent})

    paper_scores = [
        {"subject_id": g["subject_id"], "subject_name": g["subject_name"], "score": weighted_average(g["contributions"])}
        for g in paper_groups.values()
    ]

    # group by subject
    subject_groups: dict[int, dict] = {}
    for p in paper_scores:
        subject_groups.setdefault(p["subject_id"], {"subject_name": p["subject_name"], "scores": []})
        subject_groups[p["subject_id"]]["scores"].append(p["score"])

    marks = []
    for subject_id, g in subject_groups.items():
        score = round(sum(g["scores"]) / len(g["scores"]), 1)
        marks.append(ReportCardMark(subject_id=subject_id, subject_name=g["subject_name"], score=score, grade=get_letter_grade(score)))
    return marks


@dataclass
class RankingEntry:
    student_id: int
    name: str
    student_number: str
    average: float
    combination: str


def compute_report_card_ranking(students, term: str, year: int, included_result_types: list[str]) -> list[RankingEntry]:
    """Port of computeReportCardRanking() — ranks by computeReportCardMarks-derived average (0 if none)."""
    entries = []
    for student in students:
        marks = compute_report_card_marks(student.id, student.school_class_id, term, year, included_result_types)
        average = round(sum(m.score for m in marks) / len(marks), 1) if marks else 0.0
        entries.append(RankingEntry(student_id=student.id, name=student.name, student_number=student.student_number, average=average, combination=student.combination))
    entries.sort(key=lambda e: e.average, reverse=True)
    return entries


@dataclass
class ReportCardSummary:
    mean_score: float
    mean_grade: str
    mean_points: float
    result_band: int
    result_label: str


def compute_report_card_summary(marks: list[ReportCardMark]) -> ReportCardSummary:
    """Port of computeReportCardSummary()."""
    if not marks:
        return ReportCardSummary(mean_score=0, mean_grade="—", mean_points=0, result_band=0, result_label="Not yet available")
    mean_score = round(sum(m.score for m in marks) / len(marks), 1)
    mean_grade = get_letter_grade(mean_score)
    mean_points = round(sum(get_grade_points(m.grade) for m in marks) / len(marks), 4)
    result_band = get_result_band(mean_points)
    return ReportCardSummary(
        mean_score=mean_score, mean_grade=mean_grade, mean_points=mean_points,
        result_band=result_band, result_label=RESULT_BAND_LABELS[result_band],
    )


@dataclass
class PerformanceTrend:
    has_previous_data: bool
    direction: str
    previous_mean_score: float | None = None
    current_mean_score: float | None = None
    delta: float | None = None


def _resolve_historical_class_id(student_id: int, term: str, year: int, fallback_class_id: int) -> int:
    """Port of resolveHistoricalClassName()."""
    from apps.students.models import TermEnrollment

    enrollment = TermEnrollment.objects.filter(student_id=student_id, term=term, year=year).first()
    return enrollment.school_class_id if enrollment else fallback_class_id


def compute_performance_trend(student_id: int, school_class_id: int, term: str, year: int, current_marks: list[ReportCardMark], report_card_configs_qs) -> PerformanceTrend:
    """Port of computePerformanceTrend()."""
    prev_term, prev_year = get_previous_term(term, year)
    prev_class_id = _resolve_historical_class_id(student_id, prev_term, prev_year, school_class_id)
    prev_included = get_included_result_types(report_card_configs_qs, prev_term, prev_year)
    prev_marks = compute_report_card_marks(student_id, prev_class_id, prev_term, prev_year, prev_included)

    if not prev_marks or not current_marks:
        return PerformanceTrend(has_previous_data=False, direction="no-data")

    previous_mean = round(sum(m.score for m in prev_marks) / len(prev_marks), 1)
    current_mean = round(sum(m.score for m in current_marks) / len(current_marks), 1)
    delta = round(current_mean - previous_mean, 1)

    if delta > 0.5:
        direction = "improved"
    elif delta < -0.5:
        direction = "declined"
    else:
        direction = "same"

    return PerformanceTrend(
        has_previous_data=True, direction=direction,
        previous_mean_score=previous_mean, current_mean_score=current_mean, delta=delta,
    )


@dataclass
class StreamPerformanceRow:
    class_name: str
    stream: str
    mean_score: float
    student_count: int


def compute_stream_comparison(level_group: str, term: str, year: int, included_result_types: list[str]) -> list[StreamPerformanceRow]:
    """Port of computeStreamComparison()."""
    from apps.academics.models import SchoolClass

    rows = []
    for school_class in SchoolClass.objects.filter(level_group=level_group):
        class_students = list(school_class.students.all())
        ranking = compute_report_card_ranking(class_students, term, year, included_result_types)
        with_scores = [r for r in ranking if r.average > 0]
        mean_score = round(sum(r.average for r in with_scores) / len(with_scores), 1) if with_scores else 0.0
        rows.append(StreamPerformanceRow(
            class_name=school_class.name, stream=school_class.stream,
            mean_score=mean_score, student_count=len(class_students),
        ))
    return rows


# ---------------------------------------------------------------------------
# Auto-generated comments
# ---------------------------------------------------------------------------

MAX_COMMENT_CHARS = 220

CLASS_TEACHER_COMMENTS = {
    "excellent": ["{name} has had an outstanding term academically.", "Excellent, disciplined work from {name} this term."],
    "very-good": ["Very good term for {name}; consistent effort shown in class.", "{name} performed very well and participates actively."],
    "good": ["{name} has done well this term with room to reach further.", "A good, steady term for {name}."],
    "fair": ["{name} showed fair effort but needs more consistency.", "{name}'s work is fair; more focus is needed in class."],
    "weak": ["{name} needs significant support and closer attention.", "{name} is struggling and requires extra help this term."],
}
DOS_COMMENTS = {
    "excellent": ["An excellent academic performance from {name} this term.", "{name} continues to excel across subjects."],
    "very-good": ["{name} has performed very well and shows strong potential.", "A commendable, very good term for {name}."],
    "good": ["{name} has a good academic standing this term.", "Satisfactory, good performance from {name}."],
    "fair": ["{name}'s performance is fair; targeted support is recommended.", "{name} needs to put in more effort academically."],
    "weak": ["{name}'s performance this term is a serious concern.", "Urgent academic support is needed for {name}."],
}
HM_COMMENTS = {
    "excellent": ["Congratulations to {name} on an excellent term.", "{name} is a shining example of hard work this term."],
    "very-good": ["Well done, {name} — a very good term overall.", "{name} is commended for very good academic effort."],
    "good": ["{name} has had a good term; keep up the effort.", "A good term for {name}, with potential for more."],
    "fair": ["{name} is encouraged to work harder next term.", "Fair effort from {name}; more commitment is needed."],
    "weak": ["{name} must urgently improve their academic effort.", "Serious concern over {name}'s performance this term."],
}


def seed_from(student_id: int, term: str, year: int) -> int:
    """
    Bit-exact port of seedFrom(). The JS version does
    `h = (h*31 + charCode) | 0` per character — a 32-bit SIGNED integer
    with wraparound on overflow. Python ints don't overflow, so we mask to
    32 bits after each step and convert back to signed range explicitly.
    """
    s = f"{student_id}-{term}-{year}"
    h = 0
    for ch in s:
        h = (h * 31 + ord(ch)) & 0xFFFFFFFF
    if h >= 0x80000000:
        h -= 0x100000000
    return h


def _pick(options: list[str], seed: int) -> str:
    """Port of pick()."""
    return options[abs(seed) % len(options)]


def _trend_clause(trend: PerformanceTrend) -> str:
    """Port of trendClause()."""
    if trend.direction == "improved":
        return " Improving from last term."
    if trend.direction == "declined":
        return " A drop from last term — needs attention."
    if trend.direction == "same":
        return " Steady with last term."
    return ""


def generate_role_comment(role: str, student_id: int, first_name: str, summary: ReportCardSummary, trend: PerformanceTrend, term: str, year: int) -> str:
    """Port of generateRoleComment()."""
    if summary.result_band == 0:  # summary.marks was empty upstream
        return "No confirmed results yet this term."

    tier = get_performance_tier(summary.mean_score)
    bank = {"classTeacher": CLASS_TEACHER_COMMENTS, "dos": DOS_COMMENTS}.get(role, HM_COMMENTS)
    seed = seed_from(student_id, term, year)
    base = _pick(bank[tier], seed).replace("{name}", first_name)
    full = base + _trend_clause(trend)
    return full[:MAX_COMMENT_CHARS]


# ---------------------------------------------------------------------------
# Missing-marks (informational only, never blocks confirm/reject)
# ---------------------------------------------------------------------------

@dataclass
class MissingMarkStudent:
    student_id: int
    student_name: str
    student_number: str


def find_missing_marks(upload) -> list[MissingMarkStudent]:
    """
    Port of findMissingMarks(). Expected students for this upload's
    (subject, paper, class) scope:
      - if the class is O-Level AND the subject is compulsory-for-O-Level:
        the WHOLE class is expected (compulsory O-Level subjects apply by
        default, no per-student enrollment check needed).
      - otherwise (electives, and ALL A-Level subjects regardless of
        compulsory/optional): only students with an ACTIVE
        StudentSubjectEnrollment matching this subject+paper.
    Returns whichever of those expected students are missing from the
    upload's actual entries.
    """
    from apps.students.models import StudentSubjectEnrollment

    school_class = upload.school_class
    subject = upload.subject
    submitted_ids = set(upload.entries.values_list("student_id", flat=True))

    is_compulsory_o_level = school_class.level == "O-Level" and subject.type_for_level("O-Level") == "Compulsory"

    if is_compulsory_o_level:
        expected = list(school_class.students.all())
    else:
        student_ids = StudentSubjectEnrollment.objects.filter(
            subject=subject, paper_id=upload.paper_id, status="Active", student__school_class=school_class,
        ).values_list("student_id", flat=True)
        expected = list(school_class.students.filter(id__in=student_ids))

    return [
        MissingMarkStudent(student_id=s.id, student_name=s.name, student_number=s.student_number)
        for s in expected if s.id not in submitted_ids
    ]
