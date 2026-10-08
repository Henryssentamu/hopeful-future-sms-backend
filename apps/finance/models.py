from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.academics.models import LevelGroup
from apps.core.models import FinanceTerm
from apps.students.models import Student


class PaymentStatus(models.TextChoices):
    """
    Shared by fee-payment status (computed, never stored — see
    finance/services.py) and ExpenditureRecord.status (stored). The
    frontend had two identically-shaped unions (PaymentStatus/BillStatus)
    for this same concept; consolidated into one here.
    """

    CLEARED = "Cleared", "Cleared"
    PARTIAL = "Partial", "Partial"
    UNPAID = "Unpaid", "Unpaid"
    OVERPAID = "Overpaid", "Overpaid"


class IncomeSource(models.TextChoices):
    SCHOOL_FEES = "School Fees", "School Fees"
    DIRECTOR_FUNDS = "Director Funds", "Director Funds"
    DONATION = "Donation", "Donation"
    OTHER = "Other", "Other"


class ExpenditureKind(models.TextChoices):
    ONE_OFF = "One-off", "One-off"
    RECURRING = "Recurring", "Recurring"


class RecurringPeriod(models.TextChoices):
    MONTHLY = "Monthly", "Monthly"
    TERMLY = "Termly", "Termly"


class ExpenditureGroup(models.TextChoices):
    OPERATIONAL = "Operational", "Operational"
    SALARIES_AND_WAGES = "Salaries & Wages", "Salaries & Wages"
    UTILITIES = "Utilities", "Utilities"
    TRANSPORT = "Transport", "Transport"
    MAINTENANCE = "Maintenance", "Maintenance"
    OTHER = "Other", "Other"


class PaymentMethod(models.TextChoices):
    CASH = "Cash", "Cash"
    BANK = "Bank", "Bank"
    MOBILE_MONEY = "Mobile Money", "Mobile Money"


class RequirementStatus(models.TextChoices):
    BROUGHT = "Brought", "Brought"
    PARTIAL = "Partial", "Partial"
    NOT_BROUGHT = "Not Brought", "Not Brought"


class FeeStructure(models.Model):
    """
    Deliberately keyed by LEVEL GROUP ("Senior 1"), not a specific stream
    ("Senior 1 A") — tuition doesn't vary by stream. Resolve a student's fee
    structure via finance.services.get_fee_structure(student), not a direct
    level_group == student.school_class.name match.
    """

    level_group = models.CharField(max_length=10, choices=LevelGroup.choices)
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    tuition = models.PositiveIntegerField(help_text="UGX")

    class Meta:
        unique_together = [("level_group", "term", "year")]

    def __str__(self):
        return f"{self.level_group} — {self.term} {self.year}"


class FeeExtra(models.Model):
    fee_structure = models.ForeignKey(FeeStructure, on_delete=models.CASCADE, related_name="extras")
    name = models.CharField(max_length=100)
    amount = models.PositiveIntegerField(help_text="UGX")

    class Meta:
        unique_together = [("fee_structure", "name")]

    def __str__(self):
        return f"{self.name}: {self.amount}"


class StudentFeeAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="fee_assignments")
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    opted_extras = models.ManyToManyField(FeeExtra, blank=True, related_name="opted_by")

    class Meta:
        unique_together = [("student", "term", "year")]

    def __str__(self):
        return f"{self.student.name} — {self.term} {self.year}"


def generate_receipt_number():
    return f"HFSS-{uuid4().hex.upper()}"


class StudentFeeAccount(models.Model):
    """Frozen term charge or explicitly imported outstanding balance."""

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="fee_accounts")
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    class_name = models.CharField(max_length=100)
    level_group = models.CharField(max_length=10, choices=LevelGroup.choices)
    amount_due = models.PositiveIntegerField()
    source = models.CharField(max_length=15, choices=[("School fees", "School fees"), ("Opening balance", "Opening balance")])
    charge_details = models.JSONField(default=list)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["student", "term", "year"], name="unique_student_fee_account")]
        ordering = ["year", "term", "id"]


class OpeningBalanceEvidence(models.Model):
    """Pre-import evidence explains an opening balance without posting income twice."""

    account = models.ForeignKey(StudentFeeAccount, on_delete=models.PROTECT, related_name="evidence")
    kind = models.CharField(max_length=10, choices=[("Charge", "Charge"), ("Payment", "Payment")])
    amount = models.PositiveIntegerField()
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField()
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        ordering = ["date", "id"]


class FeePayment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="fee_payments")
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    amount = models.PositiveIntegerField(help_text="UGX")
    date = models.DateField()
    method = models.CharField(max_length=15, choices=PaymentMethod.choices)
    receipt_no = models.CharField(max_length=50, unique=True, default=generate_receipt_number, editable=False)
    class_name = models.CharField(max_length=100, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    requires_reconciliation = models.BooleanField(default=False)
    request_id = models.UUIDField(null=True, blank=True, unique=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-date", "-id"]

    def __str__(self):
        return f"{self.receipt_no} — {self.student.name}: {self.amount}"


class PaymentAllocation(models.Model):
    payment = models.ForeignKey(FeePayment, on_delete=models.PROTECT, related_name="allocations")
    account = models.ForeignKey(StudentFeeAccount, on_delete=models.PROTECT, related_name="allocations")
    amount = models.PositiveIntegerField()
    balance_after = models.PositiveIntegerField()
    reason = models.CharField(max_length=30)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [models.CheckConstraint(check=models.Q(amount__gt=0), name="positive_payment_allocation")]


class ExpenditureCategory(models.Model):
    name = models.CharField(max_length=150, unique=True)
    group = models.CharField(max_length=20, choices=ExpenditureGroup.choices)
    recurring = models.BooleanField(default=False)
    recurring_period = models.CharField(max_length=10, choices=RecurringPeriod.choices, blank=True)
    expected_amount = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "expenditure categories"

    def __str__(self):
        return self.name


class ExpenditureRecord(models.Model):
    category = models.ForeignKey(ExpenditureCategory, on_delete=models.PROTECT, related_name="records")
    item = models.CharField(max_length=200)
    purpose = models.CharField(max_length=255)
    amount = models.PositiveIntegerField(help_text="UGX")
    date = models.DateField()
    paid_to = models.CharField(max_length=200, blank=True)
    kind = models.CharField(max_length=10, choices=ExpenditureKind.choices)
    period = models.CharField(max_length=50, blank=True, help_text='Free text, e.g. "April 2025" or "Term 1 2025"')
    status = models.CharField(max_length=10, choices=PaymentStatus.choices)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.item} — {self.amount}"


class IncomeRecord(models.Model):
    """
    Non-fee income only — "School Fees" income must always be computed by
    summing FeePayment (see finance/services.py), never stored here.
    Enforced at the model layer via clean(), not just by seeding
    convention, so this can't silently regress.
    """

    source = models.CharField(max_length=20, choices=IncomeSource.choices)
    amount = models.PositiveIntegerField(help_text="UGX")
    date = models.DateField()
    reference = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.SET_NULL)
    term = models.CharField(max_length=10, choices=FinanceTerm.choices, blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]

    def clean(self):
        if self.source == IncomeSource.SCHOOL_FEES:
            raise ValidationError('IncomeRecord.source cannot be "School Fees" — that total is always computed by summing FeePayment, never stored as an IncomeRecord.')

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.source} — {self.amount}"


class SchoolRequirement(models.Model):
    """
    `applies_to` is a JSONField list of level-group names (or
    applies_to_all=True for "All") rather than an M2M to a lookup table —
    the 6 level-groups are a closed, never-growing label set with no
    independent identity elsewhere in the schema.
    """

    name = models.CharField(max_length=150)
    unit = models.CharField(max_length=30)
    quantity_required = models.PositiveIntegerField()
    term = models.CharField(max_length=10, choices=FinanceTerm.choices)
    year = models.PositiveIntegerField()
    applies_to_all = models.BooleanField(default=False)
    applies_to_level_groups = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.term} {self.year})"

    def applies_to(self, level_group: str) -> bool:
        return self.applies_to_all or level_group in self.applies_to_level_groups


class StudentRequirementRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name="requirement_records")
    requirement = models.ForeignKey(SchoolRequirement, on_delete=models.CASCADE, related_name="records")
    quantity_brought = models.PositiveIntegerField(default=0)
    date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = [("student", "requirement")]

    def __str__(self):
        return f"{self.student.name} — {self.requirement.name}: {self.quantity_brought}"
