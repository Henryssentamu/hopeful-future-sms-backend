from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    # Nullable — only set for TEACHER/NON_TEACHING roles. Lets the frontend
    # redirect a logged-in teacher straight to their own /teachers/:id/portal
    # without a second lookup, and lets TeacherPortal.tsx check "is this
    # profile mine" against a real id instead of a name string.
    teacher_id = serializers.SerializerMethodField()
    non_teaching_staff_id = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "role", "teacher_id", "non_teaching_staff_id"]
        read_only_fields = fields

    def get_teacher_id(self, user):
        profile = getattr(user, "teacher_profile", None)
        return profile.id if profile else None

    def get_non_teaching_staff_id(self, user):
        profile = getattr(user, "non_teaching_profile", None)
        return profile.id if profile else None


class LoginSerializer(TokenObtainPairSerializer):
    """
    Extends the standard access/refresh pair with the user's id/role/name so
    the frontend doesn't need a second round-trip after login to know who's
    signed in and what they're allowed to see.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["name"] = user.get_full_name() or user.username
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
