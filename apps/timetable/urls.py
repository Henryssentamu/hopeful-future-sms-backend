from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import TimetableConfigViewSet, TimetablePeriodViewSet, TimetableSlotViewSet

router = DefaultRouter()
router.register("configs", TimetableConfigViewSet, basename="timetable-config")
router.register("periods", TimetablePeriodViewSet, basename="timetable-period")
router.register("slots", TimetableSlotViewSet, basename="timetable-slot")

urlpatterns = [
    path("", include(router.urls)),
]
