from rest_framework import serializers

from .models import Activity, AcademicPeriod, SchoolInfo


class SchoolInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SchoolInfo
        fields = ["name", "short_name", "location", "po_box", "phone", "email", "motto"]


class AcademicPeriodSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicPeriod
        fields = ["active_term", "active_year"]


class ActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, default=None)

    class Meta:
        model = Activity
        fields = ["id", "message", "type", "actor", "actor_name", "created_at"]
        read_only_fields = fields
