from .views import StudentFeeStatementView, OpeningBalanceViewSet, OpeningBalanceEvidenceViewSet
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ExpenditureCategoryViewSet,
    ExpenditureRecordViewSet,
    FeeExtraViewSet,
    FeePaymentViewSet,
    FeeStructureViewSet,
    FinanceOverviewView,
    IncomeRecordViewSet,
    SchoolRequirementViewSet,
    StudentFeeAssignmentViewSet,
    StudentFeeStatusView,
    StudentRequirementRecordViewSet,
    StudentRequirementStatusView,
)

router = DefaultRouter()
router.register("fee-structures", FeeStructureViewSet, basename="fee-structure")
router.register("fee-extras", FeeExtraViewSet, basename="fee-extra")
router.register("fee-assignments", StudentFeeAssignmentViewSet, basename="fee-assignment")
router.register("payments", FeePaymentViewSet, basename="fee-payment")
router.register("expenditure-categories", ExpenditureCategoryViewSet, basename="expenditure-category")
router.register("expenditures", ExpenditureRecordViewSet, basename="expenditure-record")
router.register("incomes", IncomeRecordViewSet, basename="income-record")
router.register("requirements", SchoolRequirementViewSet, basename="school-requirement")
router.register("requirement-records", StudentRequirementRecordViewSet, basename="requirement-record")

router.register("opening-balances", OpeningBalanceViewSet, basename="opening-balance")
router.register("opening-balance-evidence", OpeningBalanceEvidenceViewSet, basename="opening-balance-evidence")

urlpatterns = [
    path("students/<int:student_id>/statement/", StudentFeeStatementView.as_view(), name="student-fee-statement"),
    path("student-fee-status/", StudentFeeStatusView.as_view(), name="student-fee-status"),
    path("student-requirement-status/", StudentRequirementStatusView.as_view(), name="student-requirement-status"),
    path("overview/", FinanceOverviewView.as_view(), name="finance-overview"),
    path("", include(router.urls)),
]
