"""Preserve receipts; infer charges only from exact historical enrollment/prices."""
from django.db import migrations


def backfill(apps, schema_editor):
    alias = schema_editor.connection.alias
    Enrollment = apps.get_model("students", "TermEnrollment")
    Structure = apps.get_model("finance", "FeeStructure")
    Assignment = apps.get_model("finance", "StudentFeeAssignment")
    Account = apps.get_model("finance", "StudentFeeAccount")
    Payment = apps.get_model("finance", "FeePayment")
    Allocation = apps.get_model("finance", "PaymentAllocation")
    for enrollment in Enrollment.objects.using(alias).filter(status="Enrolled").select_related("school_class").iterator():
        structure = Structure.objects.using(alias).filter(level_group=enrollment.school_class.level_group, term=enrollment.term, year=enrollment.year).first()
        if structure is None:
            continue
        details = [{"name": "Tuition", "amount": structure.tuition}]
        assignment = Assignment.objects.using(alias).filter(student_id=enrollment.student_id, term=enrollment.term, year=enrollment.year).first()
        if assignment:
            details += [{"name": e.name, "amount": e.amount} for e in assignment.opted_extras.all()]
        Account.objects.using(alias).get_or_create(student_id=enrollment.student_id, term=enrollment.term, year=enrollment.year, defaults={
            "class_name": enrollment.school_class.name, "level_group": enrollment.school_class.level_group,
            "source": "School fees", "amount_due": sum(d["amount"] for d in details), "charge_details": details,
            "notes": "Charge captured from recorded term enrollment and the exact term fee structure during migration.",
        })
    for student_id in Payment.objects.using(alias).order_by().values_list("student_id", flat=True).distinct():
        accounts = list(Account.objects.using(alias).filter(student_id=student_id).order_by("year", "term", "id"))
        remaining = {a.id: a.amount_due for a in accounts}
        credits = []
        for payment in Payment.objects.using(alias).filter(student_id=student_id).order_by("date", "id"):
            target = next((a for a in accounts if a.term == payment.term and a.year == payment.year), None)
            if target is None:
                payment.requires_reconciliation = True
                payment.save(using=alias, update_fields=["requires_reconciliation"])
                continue
            payment.class_name = target.class_name
            payment.save(using=alias, update_fields=["class_name"])
            amount = min(payment.amount, remaining[target.id])
            if amount:
                remaining[target.id] -= amount
                Allocation.objects.using(alias).create(payment_id=payment.pk, account_id=target.pk, amount=amount,
                    balance_after=remaining[target.pk], reason="Legacy designated term")
            credits.append((payment, payment.amount - amount))
        # Preserve designated-term payments before settling their genuine excess.
        for payment, credit in credits:
            for account in accounts:
                amount = min(credit, remaining[account.pk])
                if amount:
                    remaining[account.pk] -= amount
                    Allocation.objects.using(alias).create(payment_id=payment.pk, account_id=account.pk, amount=amount,
                        balance_after=remaining[account.pk], reason="Legacy excess to oldest debt")
                    credit -= amount
                if not credit:
                    break


class Migration(migrations.Migration):
    dependencies = [("finance", "0003_feepayment_requires_reconciliation")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
