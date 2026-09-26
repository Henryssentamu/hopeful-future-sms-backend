from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from .health import live, ready

urlpatterns = [
    path("health/live/", live, name="health-live"),
    path("health/ready/", ready, name="health-ready"),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="docs"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/staff/", include("apps.staff.urls")),
    path("api/academics/", include("apps.academics.urls")),
    path("api/students/", include("apps.students.urls")),
    path("api/results/", include("apps.results.urls")),
    path("api/finance/", include("apps.finance.urls")),
    path("api/timetable/", include("apps.timetable.urls")),
    path("api/notifications/", include("apps.notifications.urls")),
    path("api/core/", include("apps.core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
