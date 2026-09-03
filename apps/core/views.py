from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdmin

from .models import Activity, AcademicPeriod, SchoolInfo
from .serializers import ActivitySerializer, AcademicPeriodSerializer, SchoolInfoSerializer


class SchoolInfoView(APIView):
    """GET (any authenticated user) / PATCH (admin only) the single SchoolInfo row."""

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsAdmin()]

    def get(self, request):
        return Response(SchoolInfoSerializer(SchoolInfo.load()).data)

    def patch(self, request):
        obj = SchoolInfo.load()
        serializer = SchoolInfoSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class AcademicPeriodView(APIView):
    """
    GET (any authenticated user) / PATCH (admin only) the single active
    term/year — replaces the frontend's localStorage-only concept with a
    real, shared, server-side setting.
    """

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsAdmin()]

    def get(self, request):
        return Response(AcademicPeriodSerializer(AcademicPeriod.load()).data)

    def patch(self, request):
        obj = AcademicPeriod.load()
        serializer = AcademicPeriodSerializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ActivityListView(generics.ListAPIView):
    """GET /api/core/activities/ — recent activity feed for the dashboard."""

    queryset = Activity.objects.all()[:50]
    serializer_class = ActivitySerializer
    permission_classes = [permissions.IsAuthenticated]
