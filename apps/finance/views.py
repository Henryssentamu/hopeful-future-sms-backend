from .ledger import account_rows, payment_credit, period_key, synchronize_accounts
from .models import StudentFeeAccount, OpeningBalanceEvidence
from .serializers import OpeningBalanceSerializer, OpeningBalanceEvidenceSerializer, FinancePeriodSerializer
from django.shortcuts import get_object_or_404
from django.db import transaction
from apps.students.models import TermEnrollment
from rest_framework import mixins, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsBursarOrAdmin
from apps.core.models import FinanceTerm
from apps.core.services import get_previous_term
from apps.students.models import Student
from apps.students.services import is_enrolled_for_term

from .models import (
    ExpenditureCategory,
    ExpenditureRecord,
    FeeExtra,
    FeePayment,
    FeeStructure,
    IncomeRecord,
    SchoolRequirement,
    StudentFeeAssignment,
    StudentRequirementRecord,
)
from .serializers import (
    ExpenditureCategorySerializer,
    ExpenditureRecordSerializer,
    FeeExtraSerializer,
    FeePaymentSerializer,
    FeeStructureSerializer,
    IncomeRecordSerializer,
    SchoolRequirementSerializer,
    StudentFeeAssignmentSerializer,
    StudentRequirementRecordSerializer,
)
from .services import (
    extract_term_from_period,
    extract_year_from_period,
    paid_by_student,
    payment_status,
    requirement_status,
    school_fees_income,
    student_due,
)


class ReadAllWriteBursarOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return IsBursarOrAdmin().has_permission(request, view)


class FeeStructureViewSet(viewsets.ModelViewSet):
    queryset = FeeStructure.objects.prefetch_related("extras")
    serializer_class = FeeStructureSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["level_group", "term", "year"]

    @transaction.atomic
    def perform_create(self, serializer):
        structure = serializer.save()
        for student_id in TermEnrollment.objects.filter(term=structure.term, year=structure.year,
                school_class__level_group=structure.level_group, status="Enrolled").order_by("student_id").values_list("student_id", flat=True):
            synchronize_accounts(student_id, self.request.user)

    def perform_update(self, serializer):
        structure = serializer.instance
        if StudentFeeAccount.objects.filter(term=structure.term, year=structure.year, level_group=structure.level_group, source="School fees").exists():
            raise ValidationError("This fee structure has posted student charges and cannot be changed retroactively.")
        serializer.save()

    def perform_destroy(self, instance):
        if StudentFeeAccount.objects.filter(term=instance.term, year=instance.year, level_group=instance.level_group, source="School fees").exists():
            raise ValidationError("This fee structure has posted charges and cannot be deleted.")
        instance.delete()


class FeeExtraViewSet(viewsets.ModelViewSet):
    queryset = FeeExtra.objects.select_related("fee_structure")
    serializer_class = FeeExtraSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["fee_structure"]


class StudentFeeAssignmentViewSet(viewsets.ModelViewSet):
    queryset = StudentFeeAssignment.objects.select_related("student").prefetch_related("opted_extras")
    serializer_class = StudentFeeAssignmentSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["student", "term", "year"]

    def perform_destroy(self, instance):
        if StudentFeeAccount.objects.filter(student=instance.student, term=instance.term, year=instance.year).exists():
            raise ValidationError("This fee assignment has posted charges and cannot be deleted.")
        instance.delete()


class FeePaymentViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = FeePayment.objects.select_related("student").prefetch_related("allocations__account")
    serializer_class = FeePaymentSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["student", "term", "year", "method", "receipt_no"]
    search_fields = ["receipt_no", "student__student_number", "student__name"]

    @action(detail=True, methods=["post"])
    def reconcile(self, request, pk=None):
        from .ledger import reconcile_legacy_payment
        payment = self.get_object()
        return Response(self.get_serializer(reconcile_legacy_payment(payment.pk, request.user)).data)



class ExpenditureCategoryViewSet(viewsets.ModelViewSet):
    queryset = ExpenditureCategory.objects.all()
    serializer_class = ExpenditureCategorySerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]


class ExpenditureRecordViewSet(viewsets.ModelViewSet):
    queryset = ExpenditureRecord.objects.select_related("category")
    serializer_class = ExpenditureRecordSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["category", "status", "kind"]


class IncomeRecordViewSet(viewsets.ModelViewSet):
    queryset = IncomeRecord.objects.all()
    serializer_class = IncomeRecordSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["source", "term", "year"]


class SchoolRequirementViewSet(viewsets.ModelViewSet):
    queryset = SchoolRequirement.objects.all()
    serializer_class = SchoolRequirementSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["term", "year"]


class StudentRequirementRecordViewSet(viewsets.ModelViewSet):
    queryset = StudentRequirementRecord.objects.select_related("student", "requirement")
    serializer_class = StudentRequirementRecordSerializer
    permission_classes = [ReadAllWriteBursarOrAdmin]
    filterset_fields = ["student", "requirement"]


class StudentFeeStatusView(APIView):
    """
    GET /api/finance/student-fee-status/?term=&year=&class=&status=
    Read-only, computed — port of Accounts.tsx's StudentFeesTab rows: due,
    paid, balance, status, and the previous term's outstanding balance.
    """

    permission_classes = [IsBursarOrAdmin]

    def get(self, request):
        period = FinancePeriodSerializer(data=request.query_params)
        period.is_valid(raise_exception=True)
        term, year = period.validated_data["term"], period.validated_data["year"]
        rows = []
        for student in Student.objects.select_related("school_class").prefetch_related("fee_accounts", "fee_payments"):
            accounts = account_rows(student)
            current = next((a for a in accounts if a["term"] == term and a["year"] == year), None)
            due = current["due"] if current else 0
            paid = current["paid"] if current else 0
            credit = sum(payment_credit(p) for p in student.fee_payments.all())
            previous = sum(a["balance"] for a in accounts if period_key(a["term"], a["year"]) < period_key(term, year))
            enrollment = student.term_enrollments.filter(term=term, year=year).select_related("school_class").first()
            school_class = enrollment.school_class if enrollment else student.school_class
            rows.append({
                "student_id": student.pk, "student_number": student.student_number, "name": student.name,
                "class_name": current["class_name"] if current else school_class.name, "level": school_class.level,
                "due": due, "paid": paid, "balance": due - paid,
                "status": "Overpaid" if credit and not previous and due == paid else payment_status(due, paid),
                "prev_balance": previous, "credit": credit, "fee_configured": current is not None,
                "enrolled": bool(enrollment and enrollment.status == "Enrolled"),
            })
        for param, field in (("status", "status"), ("class", "class_name"), ("level", "level")):
            if request.query_params.get(param):
                rows = [r for r in rows if r[field] == request.query_params[param]]
        return Response(rows)


class StudentFeeStatementView(APIView):
    permission_classes = [IsBursarOrAdmin]

    def get(self, request, student_id):
        student = get_object_or_404(Student, pk=student_id)
        accounts = account_rows(student)
        evidence = OpeningBalanceEvidence.objects.filter(account__student=student)
        payments = student.fee_payments.select_related("student").prefetch_related("allocations__account")
        return Response({
            "student_id": student.pk, "student_number": student.student_number, "name": student.name,
            "accounts": accounts, "payments": FeePaymentSerializer(payments, many=True).data,
            "evidence": OpeningBalanceEvidenceSerializer(evidence, many=True).data,
            "total_balance": sum(a["balance"] for a in accounts),
            "credit": sum(payment_credit(p) for p in payments),
        })


class OpeningBalanceViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = StudentFeeAccount.objects.filter(source="Opening balance")
    permission_classes = [IsBursarOrAdmin]
    serializer_class = OpeningBalanceSerializer
    filterset_fields = ["student", "term", "year"]


class OpeningBalanceEvidenceViewSet(mixins.CreateModelMixin, viewsets.ReadOnlyModelViewSet):
    queryset = OpeningBalanceEvidence.objects.select_related("account")
    permission_classes = [IsBursarOrAdmin]
    serializer_class = OpeningBalanceEvidenceSerializer
    filterset_fields = ["account"]

    def perform_create(self, serializer):
        serializer.save(recorded_by=self.request.user)


class FinanceOverviewView(APIView):
    """
    GET /api/finance/overview/?term=&year= — income-by-source (with
    computed School Fees) and expenditure-by-group totals. Expenditure
    records are matched to the requested term/year via
    extract_term_from_period/extract_year_from_period, since
    ExpenditureRecord.period is free text (e.g. "April 2025") rather than
    real term/year columns — see finance/services.py.
    """

    permission_classes = [IsBursarOrAdmin]

    def get(self, request):
        term = request.query_params.get("term", FinanceTerm.TERM_1)
        year = int(request.query_params.get("year", 2025))

        income_by_source = {"School Fees": school_fees_income(term, year)}
        for rec in IncomeRecord.objects.filter(term=term, year=year):
            income_by_source[rec.source] = income_by_source.get(rec.source, 0) + rec.amount

        expenditure_by_group = {}
        for rec in ExpenditureRecord.objects.select_related("category"):
            rec_year = extract_year_from_period(rec.period, rec.date.isoformat())
            rec_term = extract_term_from_period(rec.period, rec.date.isoformat())
            if rec_year == year and rec_term == term:
                group = rec.category.group
                expenditure_by_group[group] = expenditure_by_group.get(group, 0) + rec.amount

        return Response({
            "income_by_source": income_by_source,
            "expenditure_by_group": expenditure_by_group,
            "total_income": sum(income_by_source.values()),
            "total_expenditure": sum(expenditure_by_group.values()),
        })


class StudentRequirementStatusView(APIView):
    """
    GET /api/finance/student-requirement-status/?term=&year=&class=&status=
    Read-only, computed — port of Accounts.tsx's RequirementsTab rows.
    """

    permission_classes = [IsBursarOrAdmin]

    def get(self, request):
        term = request.query_params.get("term", FinanceTerm.TERM_1)
        year = int(request.query_params.get("year", 2025))
        prev_term, prev_year = get_previous_term(term, year)

        term_reqs = list(SchoolRequirement.objects.filter(term=term, year=year))
        prev_reqs = list(SchoolRequirement.objects.filter(term=prev_term, year=prev_year))

        qs = Student.objects.select_related("school_class")
        class_filter = request.query_params.get("class")
        if class_filter:
            qs = qs.filter(school_class__name=class_filter)

        rows = []
        for student in qs:
            level_group = student.school_class.level_group
            applicable = [r for r in term_reqs if r.applies_to(level_group)]
            total_required = sum(r.quantity_required for r in applicable)
            records = {
                rec.requirement_id: rec.quantity_brought
                for rec in StudentRequirementRecord.objects.filter(student=student, requirement__in=applicable)
            }
            total_brought = sum(records.get(r.id, 0) for r in applicable)
            status = requirement_status(total_required, total_brought)

            prev_applicable = [r for r in prev_reqs if r.applies_to(level_group)]
            prev_required = sum(r.quantity_required for r in prev_applicable)
            prev_records = {
                rec.requirement_id: rec.quantity_brought
                for rec in StudentRequirementRecord.objects.filter(student=student, requirement__in=prev_applicable)
            }
            prev_brought = sum(prev_records.get(r.id, 0) for r in prev_applicable)
            prev_outstanding = max(0, prev_required - prev_brought)

            rows.append({
                "student_id": student.id,
                "student_number": student.student_number,
                "name": student.name,
                "class_name": student.school_class.name,
                "total_required": total_required,
                "total_brought": total_brought,
                "status": status,
                "prev_outstanding": prev_outstanding,
                "enrolled": is_enrolled_for_term(student.id, term, year),
            })

        status_filter = request.query_params.get("status")
        if status_filter:
            rows = [r for r in rows if r["status"] == status_filter]

        return Response(rows)
