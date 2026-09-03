"""
Port of the finance business logic scattered across src/pages/Accounts.tsx
and src/data/mockData.ts. `getFeeStructure`'s fallback-to-most-recent
behavior, the "School Fees income is always summed from FeePayment, never
stored" derivation rule, and the free-text period-parsing calendar mapping
are all preserved here exactly.
"""

import re

from django.db.models import Sum

from apps.academics.models import LevelGroup
from apps.core.models import FinanceTerm

from .models import FeePayment, FeeStructure, PaymentStatus, RequirementStatus, StudentFeeAssignment

_MONTH_TO_TERM = {
    "jan": FinanceTerm.TERM_1, "feb": FinanceTerm.TERM_1, "mar": FinanceTerm.TERM_1, "apr": FinanceTerm.TERM_1,
    "may": FinanceTerm.TERM_2, "jun": FinanceTerm.TERM_2, "jul": FinanceTerm.TERM_2, "aug": FinanceTerm.TERM_2,
    "sep": FinanceTerm.TERM_3, "oct": FinanceTerm.TERM_3, "nov": FinanceTerm.TERM_3, "dec": FinanceTerm.TERM_3,
}
_MONTH_NUM_TO_TERM = {
    **{m: FinanceTerm.TERM_1 for m in (1, 2, 3, 4)},
    **{m: FinanceTerm.TERM_2 for m in (5, 6, 7, 8)},
    **{m: FinanceTerm.TERM_3 for m in (9, 10, 11, 12)},
}


def extract_year_from_period(period: str | None, fallback: str | None = None) -> int | None:
    """Port of extractYearFromPeriod(): regex-extracts a 20xx year from
    `period`; else takes the first 4 chars of `fallback` (a YYYY-MM-DD
    date string)."""
    if period:
        m = re.search(r"20\d{2}", period)
        if m:
            return int(m.group())
    if fallback and len(fallback) >= 4 and fallback[:4].isdigit():
        return int(fallback[:4])
    return None


def extract_term_from_period(period: str | None, date: str | None = None) -> str | None:
    """Port of extractTermFromPeriod(): literal 'Term 1/2/3' in `period` first,
    then an English month name embedded in `period`, then falls back to
    `date`'s month number. Hardcodes the Ugandan 3-term calendar
    (Jan-Apr->Term1, May-Aug->Term2, Sep-Dec->Term3)."""
    if period:
        m = re.search(r"Term\s*([123])", period, re.IGNORECASE)
        if m:
            return {"1": FinanceTerm.TERM_1, "2": FinanceTerm.TERM_2, "3": FinanceTerm.TERM_3}[m.group(1)]
        lowered = period.lower()
        for month_key, term in _MONTH_TO_TERM.items():
            if month_key in lowered:
                return term
    if date:
        try:
            month = int(date[5:7])
            return _MONTH_NUM_TO_TERM.get(month)
        except (ValueError, IndexError):
            return None
    return None


def get_fee_structure(level_group: str, term: str, year: int) -> FeeStructure | None:
    """Port of getFeeStructure(): exact (level_group, term, year) match, else
    the most-recently-defined structure for that level_group (sorted by
    year desc, then term desc) so a newly-activated term still shows a
    sensible default rather than nothing."""
    exact = FeeStructure.objects.filter(level_group=level_group, term=term, year=year).first()
    if exact:
        return exact
    term_order = {FinanceTerm.TERM_1: 1, FinanceTerm.TERM_2: 2, FinanceTerm.TERM_3: 3}
    candidates = list(FeeStructure.objects.filter(level_group=level_group))
    if not candidates:
        return None
    candidates.sort(key=lambda f: (f.year, term_order[f.term]), reverse=True)
    return candidates[0]


def student_due(student, term: str, year: int) -> int:
    """Port of studentDue(): tuition + the sum of this student's opted extras
    for that term, resolved via the student's LEVEL GROUP fee structure."""
    level_group = student.school_class.level_group
    fs = get_fee_structure(level_group, term, year)
    if not fs:
        return 0
    assignment = StudentFeeAssignment.objects.filter(student=student, term=term, year=year).first()
    extras_total = sum(e.amount for e in assignment.opted_extras.all()) if assignment else 0
    return fs.tuition + extras_total


def paid_by_student(student, term: str, year: int) -> int:
    return FeePayment.objects.filter(student=student, term=term, year=year).aggregate(total=Sum("amount"))["total"] or 0


def payment_status(due: int, paid: int) -> str:
    """Port of paymentStatus()."""
    if paid == 0:
        return PaymentStatus.UNPAID
    if paid < due:
        return PaymentStatus.PARTIAL
    if paid == due:
        return PaymentStatus.CLEARED
    return PaymentStatus.OVERPAID


def requirement_status(required: int, brought: int) -> str:
    """Port of requirementStatus()."""
    if brought == 0:
        return RequirementStatus.NOT_BROUGHT
    if brought < required:
        return RequirementStatus.PARTIAL
    return RequirementStatus.BROUGHT


def school_fees_income(term: str, year: int) -> int:
    """
    The "School Fees" income total — ALWAYS computed by summing FeePayment
    for the term/year, never stored as an IncomeRecord (see
    IncomeRecord.clean(), which enforces this at the model layer too).
    """
    return FeePayment.objects.filter(term=term, year=year).aggregate(total=Sum("amount"))["total"] or 0
