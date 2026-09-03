from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import BiometricLogViewSet, NonTeachingStaffViewSet, RecruitmentRecordViewSet, TeacherViewSet

router = DefaultRouter()
router.register("teachers", TeacherViewSet, basename="teacher")
router.register("non-teaching", NonTeachingStaffViewSet, basename="non-teaching-staff")
router.register("recruitment", RecruitmentRecordViewSet, basename="recruitment-record")
router.register("biometric-logs", BiometricLogViewSet, basename="biometric-log")

urlpatterns = [
    path("", include(router.urls)),
]
