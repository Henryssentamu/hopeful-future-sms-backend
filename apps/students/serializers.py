from rest_framework import serializers

from .models import (
    ParentInfo,
    Student,
    StudentAttendanceRecord,
    StudentSubjectEnrollment,
    TermEnrollment,
    TermRecord,
    TermSubjectMark,
)


class ParentInfoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParentInfo
        fields = ["id", "student", "father_name", "mother_name", "guardian", "phone", "alt_phone", "email", "location", "district"]


class StudentSubjectEnrollmentSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)
    paper_label = serializers.CharField(source="paper.paper", read_only=True, default=None)

    class Meta:
        model = StudentSubjectEnrollment
        fields = ["id", "student", "subject", "subject_name", "paper", "paper_label", "type", "status", "score", "grade"]


class TermSubjectMarkSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source="subject.name", read_only=True)

    class Meta:
        model = TermSubjectMark
        fields = ["id", "subject", "subject_name", "score", "grade"]


class TermRecordSerializer(serializers.ModelSerializer):
    marks = TermSubjectMarkSerializer(many=True, read_only=True)

    class Meta:
        model = TermRecord
        fields = [
            "id", "student", "term", "year", "class_position", "total_students",
            "average", "class_teacher_comment", "dos_comment", "hm_comment", "marks",
        ]
        read_only_fields = ["class_position", "total_students", "average", "marks"]


class UpdateCommentSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["classTeacher", "dos", "hm"])
    comment = serializers.CharField(allow_blank=True, max_length=220)


class TermEnrollmentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)

    class Meta:
        model = TermEnrollment
        fields = [
            "id", "student", "school_class", "class_name", "term", "year",
            "level", "combination", "enrollment_date", "status", "notes",
        ]


class StudentAttendanceRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentAttendanceRecord
        fields = ["id", "student", "school_class", "date", "status"]


class StudentSerializer(serializers.ModelSerializer):
    class_name = serializers.CharField(source="school_class.name", read_only=True)
    level = serializers.CharField(read_only=True)
    parent_info = ParentInfoSerializer(read_only=True)
    subjects = StudentSubjectEnrollmentSerializer(source="subject_enrollments", many=True, read_only=True)

    class Meta:
        model = Student
        fields = [
            "id", "student_number", "name", "school_class", "class_name", "level", "combination",
            "performance", "email", "gender", "age", "religion", "location",
            "enrollment_date", "photo_url", "parent_info", "subjects",
        ]
        read_only_fields = ["performance"]


class StudentFinanceSerializer(serializers.ModelSerializer):
    """Minimum student identity needed by finance workflows; no family or academic records."""

    class_name = serializers.CharField(source="school_class.name", read_only=True)
    level = serializers.CharField(read_only=True)

    class Meta:
        model = Student
        fields = ["id", "student_number", "name", "school_class", "class_name", "level", "combination"]


class StudentTeacherSerializer(serializers.ModelSerializer):
    """Academic student data needed for teaching, without family or contact details."""

    class_name = serializers.CharField(source="school_class.name", read_only=True)
    level = serializers.CharField(read_only=True)
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id", "student_number", "name", "school_class", "class_name", "level",
            "combination", "performance", "photo_url", "subjects",
        ]

    def get_subjects(self, student):
        request = self.context.get("request")
        teacher = getattr(getattr(request, "user", None), "teacher_profile", None)
        if teacher is None:
            return []

        enrollments = student.subject_enrollments.all()
        if student.school_class.class_teacher_id != teacher.id:
            assigned_subject_ids = student.school_class.subject_assignments.filter(
                teacher_assignments__teacher=teacher,
            ).values_list("subject_id", flat=True)
            enrollments = enrollments.filter(subject_id__in=assigned_subject_ids)
        return StudentSubjectEnrollmentSerializer(enrollments, many=True).data
