from django.urls import path

from .views import ActivityListView, AcademicPeriodView, SchoolInfoView

urlpatterns = [
    path("school-info/", SchoolInfoView.as_view(), name="school-info"),
    path("academic-period/", AcademicPeriodView.as_view(), name="academic-period"),
    path("activities/", ActivityListView.as_view(), name="activity-list"),
]
