from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.results.views import ReportCardView

from .views import (
    ParentInfoViewSet,
    StudentAttendanceRecordViewSet,
    StudentSubjectEnrollmentViewSet,
    StudentViewSet,
    TermEnrollmentViewSet,
    TermRecordViewSet,
)

router = DefaultRouter()
router.register("", StudentViewSet, basename="student")
router.register("parent-info", ParentInfoViewSet, basename="parent-info")
router.register("subject-enrollments", StudentSubjectEnrollmentViewSet, basename="subject-enrollment")
router.register("term-enrollments", TermEnrollmentViewSet, basename="term-enrollment")
router.register("term-records", TermRecordViewSet, basename="term-record")
router.register("attendance", StudentAttendanceRecordViewSet, basename="attendance-record")

urlpatterns = [
    path("<int:pk>/report-card/", ReportCardView.as_view(), name="student-report-card"),
    path("", include(router.urls)),
]
