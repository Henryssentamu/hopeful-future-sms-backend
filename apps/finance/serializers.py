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
    class Meta:
        model = StudentFeeAssignment
        fields = ["id", "student", "term", "year", "opted_extras"]


class FeePaymentSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)

    class Meta:
        model = FeePayment
        fields = ["id", "student", "student_name", "term", "year", "amount", "date", "method", "receipt_no", "notes"]


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
