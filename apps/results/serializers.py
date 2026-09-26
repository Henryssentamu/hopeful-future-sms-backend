from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.academics.models import ClassSubjectAssignment, ResultWindow, SchoolClass, Subject, SubjectPaper
from apps.core.models import FinanceTerm, ResultType
from apps.students.models import Student, TermEnrollment

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
    term = serializers.ChoiceField(choices=FinanceTerm.choices)
    year = serializers.IntegerField(min_value=2000, max_value=2100)
    result_type = serializers.ChoiceField(choices=ResultType.choices)
    weight_percent = serializers.FloatField(min_value=0.01, max_value=100)
    entries = EntryInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        try:
            school_class = SchoolClass.objects.get(pk=attrs["school_class_id"])
        except SchoolClass.DoesNotExist:
            raise serializers.ValidationError({"school_class_id": "Class not found."})
        try:
            subject = Subject.objects.get(pk=attrs["subject_id"])
        except Subject.DoesNotExist:
            raise serializers.ValidationError({"subject_id": "Subject not found."})

        assignment = ClassSubjectAssignment.objects.filter(school_class=school_class, subject=subject).first()
        if assignment is None:
            raise serializers.ValidationError({"subject_id": "This subject is not assigned to the selected class."})

        paper = None
        if attrs.get("paper_id") is not None:
            try:
                paper = SubjectPaper.objects.get(pk=attrs["paper_id"], subject=subject)
            except SubjectPaper.DoesNotExist:
                raise serializers.ValidationError({"paper_id": "Paper does not belong to the selected subject."})

        student_ids = [entry["student_id"] for entry in attrs["entries"]]
        if len(student_ids) != len(set(student_ids)):
            raise serializers.ValidationError({"entries": "Each student may appear only once."})

        valid_student_ids = set(Student.objects.filter(pk__in=student_ids).values_list("id", flat=True))
        missing_ids = sorted(set(student_ids) - valid_student_ids)
        if missing_ids:
            raise serializers.ValidationError({"entries": f"Unknown student IDs: {missing_ids}."})

        enrolled_ids = set(TermEnrollment.objects.filter(
            student_id__in=student_ids,
            school_class=school_class,
            term=attrs["term"],
            year=attrs["year"],
            status="Enrolled",
        ).values_list("student_id", flat=True))
        out_of_scope = sorted(set(student_ids) - enrolled_ids)
        if out_of_scope:
            raise serializers.ValidationError(
                {"entries": f"Students are not enrolled in this class for the selected term/year: {out_of_scope}."}
            )

        teacher = self.context.get("teacher")
        enforce_window = self.context.get("enforce_window", True)
        if teacher and not assignment.teacher_assignments.filter(teacher=teacher).exists():
            raise serializers.ValidationError({"school_class_id": "Teacher is not assigned to this class and subject."})
        if teacher and paper:
            teacher_assignment = assignment.teacher_assignments.filter(teacher=teacher).first()
            if not teacher_assignment or paper.paper not in teacher_assignment.papers:
                raise serializers.ValidationError({"paper_id": "Teacher is not assigned to this paper."})

        if enforce_window:
            now = timezone.now()
            if not ResultWindow.objects.filter(
                result_type=attrs["result_type"], term=attrs["term"], year=attrs["year"],
                opens_at__lte=now, closes_at__gte=now,
            ).exists():
                raise serializers.ValidationError({"result_type": "The submission window is not open."})

        attrs.update({"school_class": school_class, "subject": subject, "paper": paper})
        return attrs

    def create_upload(self, teacher, status: str) -> ResultUpload:
        data = self.validated_data
        with transaction.atomic():
            upload = ResultUpload.objects.create(
                teacher=teacher,
                subject=data["subject"],
                paper=data["paper"],
                school_class=data["school_class"],
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
    entries = EntryInputSerializer(many=True, allow_empty=False)

    def validate_entries(self, entries):
        student_ids = [entry["student_id"] for entry in entries]
        if len(student_ids) != len(set(student_ids)):
            raise serializers.ValidationError("Each student may appear only once.")
        upload = self.context["upload"]
        existing_ids = set(upload.entries.values_list("student_id", flat=True))
        if set(student_ids) != existing_ids:
            raise serializers.ValidationError("Resubmission must contain exactly the original students.")
        return entries


class RejectSerializer(serializers.Serializer):
    reason = serializers.CharField()


class EditEntrySerializer(serializers.Serializer):
    score = serializers.FloatField(min_value=0, max_value=100)
