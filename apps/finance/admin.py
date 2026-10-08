from django.contrib import admin

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

admin.site.register(FeeStructure)
admin.site.register(FeeExtra)
admin.site.register(StudentFeeAssignment)
@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ["receipt_no", "student", "term", "year", "amount", "date"]
    search_fields = ["receipt_no", "student__student_number", "student__name"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

admin.site.register(ExpenditureCategory)
admin.site.register(ExpenditureRecord)
admin.site.register(IncomeRecord)
admin.site.register(SchoolRequirement)
admin.site.register(StudentRequirementRecord)
