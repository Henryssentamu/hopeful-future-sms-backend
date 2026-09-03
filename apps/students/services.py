"""Small pure lookups ported from mockData.ts, operating on TermEnrollment."""

from .models import EnrollmentStatus, TermEnrollment


def is_enrolled_for_term(student_id: int, term: str, year: int) -> bool:
    """Port of isEnrolledForTerm() — must be exactly Enrolled, not just present."""
    return TermEnrollment.objects.filter(
        student_id=student_id, term=term, year=year, status=EnrollmentStatus.ENROLLED
    ).exists()


def get_enrollment(student_id: int, term: str, year: int) -> TermEnrollment | None:
    """Port of getEnrollment() — any status."""
    return TermEnrollment.objects.filter(student_id=student_id, term=term, year=year).first()
