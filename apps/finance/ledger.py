"""Term charges and immutable payment allocations, serialized per student."""
from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import ValidationError

from apps.core.models import AcademicPeriod
from apps.students.models import Student, TermEnrollment, EnrollmentStatus
from .models import FeePayment, FeeStructure, StudentFeeAssignment, StudentFeeAccount, PaymentAllocation


def period_key(term, year):
    return int(year), int(term[-1])


def account_paid(account):
    return account.allocations.aggregate(total=Sum("amount"))["total"] or 0


def payment_credit(payment):
    if payment.requires_reconciliation:
        return 0
    return payment.amount - (payment.allocations.aggregate(total=Sum("amount"))["total"] or 0)


def projected_accounts(student):
    """Only actual enrollment and an exact fee structure can establish a charge."""
    existing = {(a.term, a.year): a for a in student.fee_accounts.all()}
    accounts = list(existing.values())
    enrollments = TermEnrollment.objects.filter(student=student, status=EnrollmentStatus.ENROLLED).select_related("school_class")
    for enrollment in enrollments:
        if (enrollment.term, enrollment.year) in existing:
            continue
        structure = FeeStructure.objects.filter(level_group=enrollment.school_class.level_group, term=enrollment.term, year=enrollment.year).first()
        if structure is None:
            continue
        details = [{"name": "Tuition", "amount": structure.tuition}]
        assignment = StudentFeeAssignment.objects.filter(student=student, term=enrollment.term, year=enrollment.year).first()
        if assignment:
            details += [{"name": e.name, "amount": e.amount} for e in assignment.opted_extras.all()]
        accounts.append(StudentFeeAccount(
            student=student, term=enrollment.term, year=enrollment.year,
            class_name=enrollment.school_class.name, level_group=enrollment.school_class.level_group,
            amount_due=sum(d["amount"] for d in details), source="School fees", charge_details=details,
        ))
    return sorted(accounts, key=lambda a: period_key(a.term, a.year))


def _freeze_accounts(student, actor=None):
    for account in projected_accounts(student):
        if account.pk is None:
            account.created_by = actor
            account.save()
    return list(student.fee_accounts.order_by("year", "term", "id"))


def _allocate(payment, accounts, reason):
    remaining = payment_credit(payment)
    for account in accounts:
        outstanding = account.amount_due - account_paid(account)
        amount = min(remaining, max(0, outstanding))
        if amount:
            PaymentAllocation.objects.create(payment=payment, account=account, amount=amount,
                balance_after=outstanding - amount, reason=reason)
            remaining -= amount
        if not remaining:
            break


def _settle_credit(student, accounts):
    for payment in student.fee_payments.filter(requires_reconciliation=False).order_by("date", "id"):
        _allocate(payment, accounts, "Oldest balance / credit")


@transaction.atomic
def synchronize_accounts(student_id, actor=None):
    student = Student.objects.select_for_update().get(pk=student_id)
    if any(payment_credit(p) for p in student.fee_payments.filter(requires_reconciliation=False)):
        accounts = _freeze_accounts(student, actor)
        _settle_credit(student, accounts)


@transaction.atomic
def record_payment(*, actor, arrears_only=False, **values):
    student = Student.objects.select_for_update().get(pk=values["student"].pk)
    request_id = values.get("request_id")
    if request_id:
        previous = FeePayment.objects.filter(request_id=request_id).first()
        if previous:
            if any(getattr(previous, key) != value for key, value in values.items()):
                raise ValidationError({"request_id": "This payment request has already been used with different details."})
            return previous
    accounts = _freeze_accounts(student, actor)
    _settle_credit(student, accounts)
    target = next((a for a in accounts if a.term == values["term"] and a.year == values["year"]), None)
    if target is None:
        raise ValidationError("Record term enrollment and its fee structure, or an opening balance, before taking payment for that term.")
    active = AcademicPeriod.load()
    previous_term = period_key(target.term, target.year) < period_key(active.active_term, active.active_year)
    if (arrears_only and not previous_term) or (previous_term and target.amount_due <= account_paid(target)):
        raise ValidationError("Previous-balance payments require an outstanding account before the active term.")
    payment = FeePayment.objects.create(**values, class_name=target.class_name, recorded_by=actor)
    _allocate(payment, [target], "Selected term")
    _allocate(payment, [a for a in accounts if a.pk != target.pk], "Overpayment to oldest balance")
    return payment


@transaction.atomic
def record_opening_balance(*, actor, school_class, **values):
    student = Student.objects.select_for_update().get(pk=values["student"].pk)
    active = AcademicPeriod.load()
    if period_key(values["term"], values["year"]) >= period_key(active.active_term, active.active_year):
        raise ValidationError("Opening balances must belong to a term before the active academic period.")
    if student.fee_accounts.filter(term=values["term"], year=values["year"]).exists():
        raise ValidationError("This term already has an account; an opening balance would duplicate its charges.")
    if student.fee_payments.filter(term=values["term"], year=values["year"]).exists():
        raise ValidationError("This term already has payments. Reconcile its existing history instead of importing another balance.")
    account = StudentFeeAccount.objects.create(**values, source="Opening balance", class_name=school_class.name,
        level_group=school_class.level_group, created_by=actor)
    _settle_credit(student, _freeze_accounts(student, actor))
    return account


def account_rows(student):
    rows = []
    running = 0
    for account in projected_accounts(student):
        paid = account_paid(account) if account.pk else 0
        balance = account.amount_due - paid
        running += balance
        rows.append({
            "id": account.pk, "term": account.term, "year": account.year, "class_name": account.class_name,
            "due": account.amount_due, "paid": paid, "balance": balance, "running_balance": running,
            "source": account.source, "charge_details": account.charge_details, "notes": account.notes,
            "frozen": account.pk is not None,
        })
    return rows


@transaction.atomic
def reconcile_legacy_payment(payment_id, actor):
    """Release a held receipt only after its exact historical charge is recorded."""
    payment = FeePayment.objects.get(pk=payment_id)
    student = Student.objects.select_for_update().get(pk=payment.student_id)
    payment.refresh_from_db()
    if not payment.requires_reconciliation:
        return payment
    accounts = _freeze_accounts(student, actor)
    target = next((a for a in accounts if a.term == payment.term and a.year == payment.year and a.source == "School fees"), None)
    if target is None:
        raise ValidationError("Record the original term enrollment and full fee structure before reconciling this receipt. An opening balance cannot substitute for the original charge.")
    payment.requires_reconciliation = False
    payment.class_name = target.class_name
    payment.save(update_fields=["requires_reconciliation", "class_name"])
    _allocate(payment, [target], "Reconciled historical receipt")
    _allocate(payment, [a for a in accounts if a.pk != target.pk], "Overpayment to oldest balance")
    return payment
