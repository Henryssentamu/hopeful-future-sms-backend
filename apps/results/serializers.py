from rest_framework import serializers

from .models import ResultEntry, ResultUpload
from .services import get_letter_grade


class ResultEntrySerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source="student.name", read_only=True)
    student_number = serializers.CharField(source="student.student_number", read_only=True)

    class Meta:
        model = ResultEntry
        fields = ["id", "student", "student_name", "student_number", "score", "grade"]
        read_only_fields = ["grade"]


class ResultUploadSerializer(serializers.ModelSerializer):
    entries = ResultEntrySerializer(many=True, read_only=True)
    teacher_name = serializers.CharField(source="teacher.user.get_full_name", read_only=True)
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    class_name = serializers.CharField(source="school_class.name", read_only=True)

    class Meta:
        model = ResultUpload
        fields = [
            "id", "teacher", "teacher_name", "subject", "subject_name", "paper", "school_class", "class_name",
            "term", "year", "result_type", "weight_percent", "upload_date", "status",
            "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at", "entries",
        ]
        read_only_fields = ["status", "upload_date", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"]


class EntryInputSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()
    score = serializers.FloatField(min_value=0, max_value=100)


class SubmitResultUploadSerializer(serializers.Serializer):
    """Port of submitResultUpload()'s input shape — also reused by
    enter_and_confirm (DOS fast-path)."""

    subject_id = serializers.IntegerField()
    paper_id = serializers.IntegerField(required=False, allow_null=True)
    school_class_id = serializers.IntegerField()
    term = serializers.CharField()
    year = serializers.IntegerField()
    result_type = serializers.CharField()
    weight_percent = serializers.FloatField()
    entries = EntryInputSerializer(many=True)

    def create_upload(self, teacher, status: str) -> ResultUpload:
        data = self.validated_data
        upload = ResultUpload.objects.create(
            teacher=teacher,
            subject_id=data["subject_id"],
            paper_id=data.get("paper_id"),
            school_class_id=data["school_class_id"],
            term=data["term"],
            year=data["year"],
            result_type=data["result_type"],
            weight_percent=data["weight_percent"],
            status=status,
        )
        ResultEntry.objects.bulk_create([
            ResultEntry(upload=upload, student_id=e["student_id"], score=e["score"], grade=get_letter_grade(e["score"]))
            for e in data["entries"]
        ])
        return upload


class ResendResultUploadSerializer(serializers.Serializer):
    entries = EntryInputSerializer(many=True)


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField()


class EditEntrySerializer(serializers.Serializer):
    score = serializers.FloatField(min_value=0, max_value=100)
