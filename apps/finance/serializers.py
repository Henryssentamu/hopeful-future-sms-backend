from apps.academics.models import SchoolClass
from apps.core.models import FinanceTerm
from .ledger import record_payment, record_opening_balance, payment_credit
from .models import StudentFeeAccount, PaymentAllocation, OpeningBalanceEvidence
from rest_framework import serializers

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


class FeeExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeExtra
        fields = ["id", "fee_structure", "name", "amount"]


class FeeStructureSerializer(serializers.ModelSerializer):
    extras = FeeExtraSerializer(many=True, read_only=True)

    class Meta:
        model = FeeStructure
        fields = ["id", "level_group", "term", "year", "tuition", "extras"]


class StudentFeeAssignmentSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        student = attrs.get("student", getattr(self.instance, "student", None))
        term = attrs.get("term", getattr(self.instance, "term", None))
        year = attrs.get("year", getattr(self.instance, "year", None))
        original_posted = self.instance is not None and StudentFeeAccount.objects.filter(
            student=self.instance.student, term=self.instance.term, year=self.instance.year,
        ).exists()
        if original_posted or StudentFeeAccount.objects.filter(student=student, term=term, year=year).exists():
            raise serializers.ValidationError("This term has posted charges; its extra-fee assignment cannot be rewritten.")
        for extra in attrs.get("opted_extras", []):
            if extra.fee_structure.term != term or extra.fee_structure.year != year:
                raise serializers.ValidationError({"opted_extras": "Extras must belong to the selected term and year."})
        return attrs

    class Meta:
        model = StudentFeeAssignment
        fields = ["id", "student", "term", "year", "opted_extras"]


class PaymentAllocationSerializer(serializers.ModelSerializer):
    term = serializers.CharField(source="account.term", read_only=True)
    year = serializers.IntegerField(source="account.year", read_only=True)
    class_name = serializers.CharField(source="account.class_name", read_only=True)

    class Meta:
        model = PaymentAllocation
        fields = ["id", "account", "term", "year", "class_name", "amount", "balance_after", "reason", "created_at"]


class FeePaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)
    allocations = PaymentAllocationSerializer(many=True, read_only=True)
    credit = serializers.SerializerMethodField()
    amount = serializers.IntegerField(min_value=1)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    request_id = serializers.UUIDField(required=True)
    arrears_only = serializers.BooleanField(default=False, write_only=True)

    class Meta:
        model = FeePayment
        fields = ["id", "student", "student_name", "student_number", "class_name", "term", "year", "amount", "date", "method", "receipt_no", "notes", "allocations", "credit", "recorded_at", "recorded_by", "request_id", "requires_reconciliation", "arrears_only"]
        read_only_fields = ["receipt_no", "class_name", "recorded_at", "recorded_by", "requires_reconciliation"]

    def get_credit(self, payment):
        return payment_credit(payment)

    def create(self, validated_data):
        return record_payment(actor=self.context["request"].user, **validated_data)


class OpeningBalanceSerializer(serializers.ModelSerializer):
    school_class = serializers.PrimaryKeyRelatedField(queryset=SchoolClass.objects.all(), write_only=True)
    amount_due = serializers.IntegerField(min_value=1)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    notes = serializers.CharField(allow_blank=False)

    class Meta:
        model = StudentFeeAccount
        fields = ["id", "student", "term", "year", "school_class", "class_name", "amount_due", "source", "notes", "created_at"]
        read_only_fields = ["class_name", "source", "created_at"]
        validators = []

    def create(self, validated_data):
        return record_opening_balance(actor=self.context["request"].user, **validated_data)


class OpeningBalanceEvidenceSerializer(serializers.ModelSerializer):
    amount = serializers.IntegerField(min_value=1)

    class Meta:
        model = OpeningBalanceEvidence
        fields = ["id", "account", "kind", "amount", "date", "reference", "notes", "recorded_at", "recorded_by"]
        read_only_fields = ["recorded_at", "recorded_by"]

    def validate_account(self, account):
        if account.source != "Opening balance":
            raise serializers.ValidationError("Historical evidence belongs to an imported opening balance.")
        return account


class FinancePeriodSerializer(serializers.Serializer):
    term = serializers.ChoiceField(choices=FinanceTerm.choices)
    year = serializers.IntegerField(min_value=2000, max_value=2100)


class ExpenditureCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenditureCategory
        fields = ["id", "name", "group", "recurring", "recurring_period", "expected_amount", "description"]


class ExpenditureRecordSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)

    class Meta:
        model = ExpenditureRecord
        fields = [
            "id", "category", "category_name", "item", "purpose", "amount",
            "date", "paid_to", "kind", "period", "status",
        ]


class IncomeRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncomeRecord
        fields = ["id", "source", "amount", "date", "reference", "description", "student", "term", "year"]

    def validate_source(self, value):
        if value == "School Fees":
            raise serializers.ValidationError(
                'School Fees income is always computed by summing FeePayment — it cannot be created as an IncomeRecord.'
            )
        return value


class SchoolRequirementSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolRequirement
        fields = ["id", "name", "unit", "quantity_required", "term", "year", "applies_to_all", "applies_to_level_groups", "notes"]


class StudentRequirementRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentRequirementRecord
        fields = ["id", "student", "requirement", "quantity_brought", "date", "notes"]
