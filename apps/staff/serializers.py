from rest_framework import serializers

from apps.accounts.serializers import UserSerializer

from .models import BiometricLog, NonTeachingStaff, RecruitmentRecord, RecruitmentStatus, Teacher


class TeacherSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = Teacher
        fields = ["id", "user", "name", "email", "attendance", "performance", "phone", "status", "join_date"]


class TeacherDirectorySerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Teacher
        fields = ["id", "user_id", "name"]


class NonTeachingStaffSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    name = serializers.CharField(source="user.get_full_name", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = NonTeachingStaff
        fields = ["id", "user", "name", "email", "job_title", "department", "phone", "join_date", "status"]


class RecruitmentRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruitmentRecord
        fields = ["id", "candidate_name", "staff_type", "role", "email", "phone", "applied_date", "status", "notes", "hired_user"]
        read_only_fields = ["hired_user"]

    def validate_status(self, value):
        # Pending <-> Rejected is a plain status flip, fine via PATCH. Hired
        # has real side effects (materializes a User+Teacher/NonTeachingStaff
        # — see services.hire_candidate) and must only happen through the
        # dedicated hire/ action, never by directly setting this field.
        if value == RecruitmentStatus.HIRED:
            raise serializers.ValidationError("Use the hire/ action to mark a candidate Hired.")
        return value


class BiometricLogSerializer(serializers.ModelSerializer):
    staff_name = serializers.CharField(source="staff.get_full_name", read_only=True)
    staff_role = serializers.CharField(source="staff.role", read_only=True)
    hours = serializers.FloatField(read_only=True)

    class Meta:
        model = BiometricLog
        fields = ["id", "staff", "staff_name", "staff_role", "date", "sign_in", "sign_out", "hours"]
