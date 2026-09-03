from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ResultUploadViewSet

router = DefaultRouter()
router.register("uploads", ResultUploadViewSet, basename="result-upload")

urlpatterns = [
    path("", include(router.urls)),
]
