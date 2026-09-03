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
admin.site.register(FeePayment)
admin.site.register(ExpenditureCategory)
admin.site.register(ExpenditureRecord)
admin.site.register(IncomeRecord)
admin.site.register(SchoolRequirement)
admin.site.register(StudentRequirementRecord)
