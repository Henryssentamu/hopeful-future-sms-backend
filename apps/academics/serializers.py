from rest_framework import serializers

from .models import (
    ClassSubjectAssignment,
    Department,
    ReportCardConfig,
    ResultWindow,
    SchoolClass,
    Subject,
    SubjectPaper,
    TeacherAssignment,
)


class SubjectPaperSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubjectPaper
        fields = ["id", "paper", "label"]


class SubjectSerializer(serializers.ModelSerializer):
    papers = SubjectPaperSerializer(many=True, read_only=True)

    class Meta:
        model = Subject
        fields = [
            "id", "subject_code", "name", "o_level_type", "a_level_type",
            "level", "status", "category", "students_enrolled", "description", "papers",
        ]


class DepartmentSerializer(serializers.ModelSerializer):
    subject_names = serializers.SlugRelatedField(source="subjects", slug_field="name", many=True, read_only=True)
    head_teacher_name = serializers.CharField(source="head_teacher.user.get_full_name", read_only=True, default=None)

    class Meta:
        model = Department
        fields = ["id", "name", "subjects", "subject_names", "head_teacher", "head_teacher_name"]
        extra_kwargs = {"subjects": {"write_only": True}}


class TeacherAssignmentSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)

    class Meta:
        model = TeacherAssignment
        fields = ["id", "class_subject_assignment", "teacher", "teacher_name", "papers"]


class ClassSubjectAssignmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    teacher_assignments = TeacherAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = ClassSubjectAssignment
        fields = ["id", "school_class", "subject", "subject_name", "type", "teacher_assignments"]


class SchoolClassSerializer(serializers.ModelSerializer):
    class_teacher_name = serializers.CharField(source="class_teacher.user.get_full_name", read_only=True, default=None)
    subject_assignments = ClassSubjectAssignmentSerializer(many=True, read_only=True)

    class Meta:
        model = SchoolClass
        fields = [
            "id", "name", "level_group", "stream", "level",
            "class_teacher", "class_teacher_name", "subject_assignments",
        ]


class AssignTeacherSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    teacher_id = serializers.IntegerField()
    papers = serializers.ListField(child=serializers.CharField(), allow_empty=True)
    assignment_type = serializers.ChoiceField(choices=["Compulsory", "Optional"], default="Compulsory")


class RemoveTeacherSerializer(serializers.Serializer):
    subject_id = serializers.IntegerField()
    teacher_id = serializers.IntegerField()


class ReassignClassTeacherSerializer(serializers.Serializer):
    teacher_id = serializers.IntegerField()


class ReportCardConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportCardConfig
        fields = ["id", "term", "year", "included_result_types"]


class ResultWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResultWindow
        fields = ["id", "result_type", "term", "year", "opens_at", "closes_at"]

    def validate(self, attrs):
        opens_at = attrs.get("opens_at", getattr(self.instance, "opens_at", None))
        closes_at = attrs.get("closes_at", getattr(self.instance, "closes_at", None))
        if opens_at and closes_at and closes_at <= opens_at:
            raise serializers.ValidationError({"closes_at": "Closing time must be after opening time."})
        return attrs
