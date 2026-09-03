from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    ClassSubjectAssignmentViewSet,
    DepartmentViewSet,
    ReportCardConfigViewSet,
    ResultWindowViewSet,
    SchoolClassViewSet,
    SubjectPaperViewSet,
    SubjectViewSet,
)

router = DefaultRouter()
router.register("subjects", SubjectViewSet, basename="subject")
router.register("subject-papers", SubjectPaperViewSet, basename="subject-paper")
router.register("departments", DepartmentViewSet, basename="department")
router.register("classes", SchoolClassViewSet, basename="school-class")
router.register("class-subject-assignments", ClassSubjectAssignmentViewSet, basename="class-subject-assignment")
router.register("report-card-configs", ReportCardConfigViewSet, basename="report-card-config")
router.register("result-windows", ResultWindowViewSet, basename="result-window")

urlpatterns = [
    path("", include(router.urls)),
]
