from datetime import date
from uuid import uuid4
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.academics.models import SchoolClass
from apps.core.models import AcademicPeriod
from apps.students.models import Student, TermEnrollment
from .models import FeeStructure, FeePayment, StudentFeeAccount, PaymentAllocation
from .ledger import record_payment, synchronize_accounts


class FeeLedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="bursar-ledger", role="BURSAR")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        AcademicPeriod.objects.update_or_create(pk=1, defaults={"active_term": "Term 3", "active_year": 2026})
        self.school_class = SchoolClass.objects.create(name="Senior 2 A", level="O-Level", level_group="Senior 2", stream="A")
        self.student = Student.objects.create(student_number="LEDGER-1", name="Ledger Learner", school_class=self.school_class,
            gender="Female", enrollment_date=date(2026, 9, 1))
        FeeStructure.objects.create(level_group="Senior 2", term="Term 3", year=2026, tuition=1000)
        TermEnrollment.objects.create(student=self.student, school_class=self.school_class, term="Term 3", year=2026,
            level="O-Level", status="Enrolled")

    def payment(self, amount=1000, **extra):
        payload = {"student": self.student.pk, "term": "Term 3", "year": 2026, "amount": amount,
            "date": "2026-10-01", "method": "Cash", "request_id": str(uuid4()), **extra}
        return self.client.post("/api/finance/payments/", payload, format="json")

    def opening(self, term="Term 1", amount=500):
        return self.client.post("/api/finance/opening-balances/", {"student": self.student.pk, "school_class": self.school_class.pk,
            "term": term, "year": 2026, "amount_due": amount, "notes": "Verified old ledger"}, format="json")

    def statement(self):
        response = self.client.get(f"/api/finance/students/{self.student.pk}/statement/")
        self.assertEqual(response.status_code, 200)
        return response.data

    def test_new_student_has_no_invented_previous_debt(self):
        FeeStructure.objects.create(level_group="Senior 2", term="Term 2", year=2026, tuition=800)
        response = self.client.get("/api/finance/student-fee-status/?term=Term%203&year=2026")
        self.assertEqual(response.data[0]["prev_balance"], 0)
        self.assertEqual(response.data[0]["due"], 1000)
        self.assertEqual(self.statement()["accounts"][0]["term"], "Term 3")

    def test_receipt_generated_and_searchable_with_class_and_student(self):
        response = self.payment(400, receipt_no="CLIENT-MUST-NOT-CHOOSE")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["receipt_no"].startswith("HFSS-"))
        found = self.client.get("/api/finance/payments/", {"receipt_no": response.data["receipt_no"]})
        self.assertEqual(found.data["count"], 1)
        self.assertEqual(found.data["results"][0]["class_name"], "Senior 2 A")
        self.assertEqual(found.data["results"][0]["student_number"], "LEDGER-1")

    def test_excess_settles_oldest_debt_and_retains_allocation_balances(self):
        self.assertEqual(self.opening("Term 1", 500).status_code, 201)
        self.assertEqual(self.opening("Term 2", 400).status_code, 201)
        response = self.payment(1700)
        self.assertEqual(response.status_code, 201, response.data)
        allocations = response.data["allocations"]
        self.assertEqual([(a["term"], a["amount"], a["balance_after"]) for a in allocations],
            [("Term 3", 1000, 0), ("Term 1", 500, 0), ("Term 2", 200, 200)])
        self.assertEqual(self.statement()["total_balance"], 200)
        self.assertEqual(FeePayment.objects.count(), 1)

    def test_remaining_credit_is_applied_when_new_term_enrollment_is_recorded(self):
        response = self.payment(1500)
        self.assertEqual(response.data["credit"], 500)
        FeeStructure.objects.create(level_group="Senior 2", term="Term 1", year=2027, tuition=1000)
        admin = get_user_model().objects.create_user(username="academic-ledger", role="DOS")
        self.client.force_authenticate(admin)
        response = self.client.post("/api/students/term-enrollments/", {"student": self.student.pk, "school_class": self.school_class.pk,
            "term": "Term 1", "year": 2027, "level": "O-Level", "status": "Enrolled"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.client.force_authenticate(self.user)
        statement = self.statement()
        self.assertEqual(statement["credit"], 0)
        self.assertEqual(statement["accounts"][-1]["paid"], 500)
        self.assertEqual(statement["payments"][0]["amount"], 1500)

    def test_retry_returns_same_receipt_and_changed_request_is_rejected(self):
        token = str(uuid4())
        first = self.payment(500, request_id=token)
        second = self.payment(500, request_id=token)
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(first.data["receipt_no"], second.data["receipt_no"])
        self.assertEqual(FeePayment.objects.count(), 1)
        self.assertEqual(self.payment(600, request_id=token).status_code, 400)

    def test_failure_rolls_back_receipt_and_all_allocations(self):
        with patch("apps.finance.ledger._allocate", side_effect=RuntimeError("test rollback")):
            with self.assertRaises(RuntimeError):
                record_payment(actor=self.user, student=self.student, term="Term 3", year=2026, amount=900,
                    date=date(2026, 10, 1), method="Cash", request_id=uuid4())
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(PaymentAllocation.objects.count(), 0)
        self.assertEqual(StudentFeeAccount.objects.count(), 0)

    def test_opening_evidence_does_not_count_as_new_income_or_reduce_debt(self):
        opening = self.opening()
        self.assertEqual(opening.status_code, 201, opening.data)
        response = self.client.post("/api/finance/opening-balance-evidence/", {"account": opening.data["id"],
            "kind": "Payment", "amount": 200, "date": "2026-02-10", "reference": "OLD-1", "notes": "Old cashbook"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.statement()["accounts"][0]["balance"], 500)
        self.assertEqual(FeePayment.objects.count(), 0)
        self.assertEqual(len(self.statement()["evidence"]), 1)

    def test_duplicate_opening_and_current_term_opening_rejected(self):
        self.assertEqual(self.opening().status_code, 201)
        self.assertEqual(self.opening().status_code, 400)
        self.assertEqual(self.opening("Term 3").status_code, 400)

    def test_arrears_payment_requires_actual_previous_balance(self):
        self.assertEqual(self.payment(200, arrears_only=True).status_code, 400)
        self.opening()
        response = self.payment(500, term="Term 1", arrears_only=True)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(self.payment(100, term="Term 1", arrears_only=True).status_code, 400)

    def test_posted_history_survives_promotion_and_fee_changes(self):
        self.payment(300)
        FeeStructure.objects.filter(term="Term 3", year=2026).update(tuition=2000)
        other = SchoolClass.objects.create(name="Senior 3 B", level_group="Senior 3", stream="B", level="O-Level")
        self.student.school_class = other
        self.student.save()
        account = self.statement()["accounts"][0]
        self.assertEqual((account["class_name"], account["due"], account["paid"]), ("Senior 2 A", 1000, 300))

    def test_financial_records_cannot_be_edited_or_deleted(self):
        payment = self.payment(100).data
        url = f'/api/finance/payments/{payment["id"]}/'
        self.assertEqual(self.client.patch(url, {"amount": 1}, format="json").status_code, 405)
        self.assertEqual(self.client.delete(url).status_code, 405)

    def test_finance_is_not_available_to_teacher_or_dos(self):
        for role in ["TEACHER", "DOS"]:
            user = get_user_model().objects.create_user(username=f"ledger-{role}", role=role)
            self.client.force_authenticate(user)
            self.assertEqual(self.client.get(f"/api/finance/students/{self.student.pk}/statement/").status_code, 403)
            self.assertEqual(self.payment().status_code, 403)

    def test_invalid_money_and_periods_rejected(self):
        for amount in [0, -1, 1.5]:
            self.assertEqual(self.payment(amount).status_code, 400)
        self.assertEqual(self.client.get("/api/finance/student-fee-status/?term=Unknown&year=bad").status_code, 400)

    def test_legacy_unverified_receipt_is_held_not_spent_as_credit(self):
        FeePayment.objects.create(student=self.student, term="Term 1", year=2024, amount=1000, date=date(2024, 1, 1),
            method="Cash", receipt_no="OLD-UNKNOWN", requires_reconciliation=True)
        synchronize_accounts(self.student.pk)
        statement = self.statement()
        self.assertEqual(statement["credit"], 0)
        self.assertEqual(statement["accounts"][0]["paid"], 0)
        self.assertTrue(statement["payments"][0]["requires_reconciliation"])

    def test_legacy_reconciliation_requires_exact_history_and_preserves_receipt(self):
        payment = FeePayment.objects.create(
            student=self.student, term="Term 1", year=2024, amount=1200,
            date=date(2024, 1, 1), method="Cash", receipt_no="OLD-VERIFIED",
            requires_reconciliation=True,
        )
        url = f"/api/finance/payments/{payment.pk}/reconcile/"
        self.assertEqual(self.client.post(url).status_code, 400)
        payment.refresh_from_db()
        self.assertTrue(payment.requires_reconciliation)
        FeeStructure.objects.create(level_group="Senior 2", term="Term 1", year=2024, tuition=1000)
        TermEnrollment.objects.create(
            student=self.student, school_class=self.school_class,
            term="Term 1", year=2024, level="O-Level", status="Enrolled",
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["receipt_no"], "OLD-VERIFIED")
        self.assertEqual(response.data["amount"], 1200)
        self.assertFalse(response.data["requires_reconciliation"])
        self.assertEqual([a["amount"] for a in response.data["allocations"]], [1000, 200])
        self.assertEqual(self.client.post(url).status_code, 200)
        self.assertEqual(payment.allocations.count(), 2)

    def test_backfill_preserves_receipts_and_holds_unknown_history(self):
        from importlib import import_module
        from django.apps import apps
        from django.db import connection

        known = FeePayment.objects.create(
            student=self.student, term="Term 3", year=2026, amount=1200,
            date=date(2026, 10, 1), method="Cash", receipt_no="LEGACY-KNOWN",
        )
        unknown = FeePayment.objects.create(
            student=self.student, term="Term 1", year=2024, amount=700,
            date=date(2024, 1, 1), method="Cash", receipt_no="LEGACY-UNKNOWN",
        )
        migration = import_module("apps.finance.migrations.0004_backfill_fee_accounts")
        with connection.schema_editor(atomic=False) as editor:
            migration.backfill(apps, editor)
        known.refresh_from_db()
        unknown.refresh_from_db()
        self.assertEqual(known.receipt_no, "LEGACY-KNOWN")
        self.assertEqual(known.amount, 1200)
        self.assertEqual(known.allocations.get().amount, 1000)
        self.assertTrue(unknown.requires_reconciliation)
        self.assertFalse(unknown.allocations.exists())
        self.assertEqual(self.statement()["credit"], 200)
