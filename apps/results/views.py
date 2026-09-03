from django.utils import timezone
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import ReportCardConfig
from apps.students.models import Student

from .models import RejectedBy, ResultEntry, ResultUpload, ResultUploadStatus
from .permissions import IsClassTeacherOfScope, IsDOSOrAdmin, IsSubmittingTeacherOfScope
from .serializers import (
    EditEntrySerializer,
    RejectSerializer,
    ResendResultUploadSerializer,
    ResultUploadSerializer,
    SubmitResultUploadSerializer,
)
from .services import (
    apply_result_upload,
    compute_performance_trend,
    compute_report_card_marks,
    compute_report_card_ranking,
    compute_report_card_summary,
    compute_stream_comparison,
    find_missing_marks,
    generate_role_comment,
    get_included_result_types,
    get_letter_grade,
)


class ResultUploadViewSet(viewsets.ModelViewSet):
    """
    The results state machine. Maps 1:1 to DataContext's 9 mutator
    functions — see plan doc's endpoint table. Plain list/retrieve is open
    to any authenticated user (Teacher Portal / Class Teacher review / DOS
    Results Management all read from the same filtered list); every
    mutating action has its own specific permission check.
    """

    queryset = ResultUpload.objects.select_related("teacher__user", "subject", "school_class").prefetch_related("entries__student")
    serializer_class = ResultUploadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["school_class", "term", "year", "status", "subject", "teacher"]
    http_method_names = ["get", "post", "head", "options"]  # no generic put/patch/delete — only the actions below mutate

    def create(self, request, *args, **kwargs):
        """POST /api/results/uploads/ — submitResultUpload(). Teacher-only,
        creates as PendingClassTeacher."""
        teacher = getattr(request.user, "teacher_profile", None)
        if not teacher:
            return Response({"detail": "Only teachers can submit results."}, status=403)
        serializer = SubmitResultUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.create_upload(teacher, ResultUploadStatus.PENDING_CLASS_TEACHER)
        return Response(ResultUploadSerializer(upload).data, status=201)

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        """resendResultUpload() — submitting teacher only, only from a Rejected state."""
        upload = self.get_object()
        if upload.status not in (ResultUploadStatus.REJECTED_BY_CLASS_TEACHER, ResultUploadStatus.REJECTED_BY_DOS):
            return Response({"detail": "Can only resend a rejected upload."}, status=400)
        if not IsSubmittingTeacherOfScope().has_object_permission(request, self, upload):
            return Response({"detail": "Only the submitting teacher may resend."}, status=403)

        serializer = ResendResultUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for e in serializer.validated_data["entries"]:
            ResultEntry.objects.filter(upload=upload, student_id=e["student_id"]).update(
                score=e["score"], grade=get_letter_grade(e["score"])
            )
        upload.status = ResultUploadStatus.PENDING_CLASS_TEACHER
        upload.rejection_reason = ""
        upload.rejected_by = ""
        upload.rejected_by_name = ""
        upload.rejected_at = None
        upload.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"])
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"], url_path="class-teacher-confirm")
    def class_teacher_confirm(self, request, pk=None):
        """classTeacherConfirm() -> PendingDOS. No grade sync yet."""
        upload = self.get_object()
        if not IsClassTeacherOfScope().has_object_permission(request, self, upload):
            return Response({"detail": "Only this class's Class Teacher may confirm."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_CLASS_TEACHER:
            return Response({"detail": "Upload is not awaiting Class Teacher review."}, status=400)
        upload.status = ResultUploadStatus.PENDING_DOS
        upload.save(update_fields=["status"])
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"], url_path="class-teacher-reject")
    def class_teacher_reject(self, request, pk=None):
        """classTeacherReject()."""
        upload = self.get_object()
        if not IsClassTeacherOfScope().has_object_permission(request, self, upload):
            return Response({"detail": "Only this class's Class Teacher may reject."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_CLASS_TEACHER:
            return Response({"detail": "Upload is not awaiting Class Teacher review."}, status=400)
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload.status = ResultUploadStatus.REJECTED_BY_CLASS_TEACHER
        upload.rejection_reason = serializer.validated_data["reason"]
        upload.rejected_by = RejectedBy.CLASS_TEACHER
        upload.rejected_by_name = request.user.get_full_name() or request.user.username
        upload.rejected_at = timezone.now()
        upload.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"])
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"], url_path=r"entries/(?P<student_id>[0-9]+)")
    def edit_entry(self, request, pk=None, student_id=None):
        """editResultUploadEntry() — DOS/Admin, only while PendingDOS."""
        upload = self.get_object()
        if not IsDOSOrAdmin().has_permission(request, self):
            return Response({"detail": "DOS or Admin only."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_DOS:
            return Response({"detail": "Can only edit entries while awaiting DOS review."}, status=400)
        serializer = EditEntrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = upload.entries.filter(student_id=student_id).first()
        if not entry:
            return Response({"detail": "No entry for that student on this upload."}, status=404)
        entry.score = serializer.validated_data["score"]
        entry.grade = get_letter_grade(entry.score)
        entry.save(update_fields=["score", "grade"])
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """confirmResultUpload() — DOS/Admin. THE critical sync path: sets
        Confirmed, then runs apply_result_upload."""
        upload = self.get_object()
        if not IsDOSOrAdmin().has_permission(request, self):
            return Response({"detail": "DOS or Admin only."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_DOS:
            return Response({"detail": "Upload is not awaiting DOS review."}, status=400)
        upload.status = ResultUploadStatus.CONFIRMED
        upload.save(update_fields=["status"])
        apply_result_upload(upload)
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"], url_path="dos-reject")
    def dos_reject(self, request, pk=None):
        """dosReject()."""
        upload = self.get_object()
        if not IsDOSOrAdmin().has_permission(request, self):
            return Response({"detail": "DOS or Admin only."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_DOS:
            return Response({"detail": "Upload is not awaiting DOS review."}, status=400)
        serializer = RejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload.status = ResultUploadStatus.REJECTED_BY_DOS
        upload.rejection_reason = serializer.validated_data["reason"]
        upload.rejected_by = RejectedBy.DOS
        upload.rejected_by_name = request.user.get_full_name() or request.user.username
        upload.rejected_at = timezone.now()
        upload.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"])
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=False, methods=["post"], url_path="enter-and-confirm")
    def enter_and_confirm(self, request):
        """enterAndConfirmResult() — DOS fast-path: creates directly as
        Confirmed and applies immediately, skipping the review chain."""
        if not IsDOSOrAdmin().has_permission(request, self):
            return Response({"detail": "DOS or Admin only."}, status=403)
        teacher_id = request.data.get("teacher_id")
        if not teacher_id:
            return Response({"detail": "teacher_id is required (whose results these are being entered on behalf of)."}, status=400)
        from apps.staff.models import Teacher
        try:
            teacher = Teacher.objects.get(pk=teacher_id)
        except Teacher.DoesNotExist:
            return Response({"detail": "Teacher not found."}, status=404)

        serializer = SubmitResultUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.create_upload(teacher, ResultUploadStatus.CONFIRMED)
        apply_result_upload(upload)
        return Response(ResultUploadSerializer(upload).data, status=201)

    @action(detail=True, methods=["get"], url_path="missing-marks")
    def missing_marks(self, request, pk=None):
        """findMissingMarks() — informational only, never blocks confirm/reject."""
        upload = self.get_object()
        missing = find_missing_marks(upload)
        return Response([{"student_id": m.student_id, "student_name": m.student_name, "student_number": m.student_number} for m in missing])


class ReportCardView(APIView):
    """
    GET /api/students/{id}/report-card/?term=&year=
    The single bundled endpoint — marks, summary, trend, class ranking,
    stream comparison, and all 3 role comments together, since the
    frontend's ReportCardView.tsx is the only consumer of any of this.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, pk):
        student = Student.objects.select_related("school_class").get(pk=pk)
        term = request.query_params.get("term")
        year = int(request.query_params.get("year"))

        configs_qs = ReportCardConfig.objects.all()
        included = get_included_result_types(configs_qs, term, year)

        marks = compute_report_card_marks(student.id, student.school_class_id, term, year, included)
        summary = compute_report_card_summary(marks)
        trend = compute_performance_trend(student.id, student.school_class_id, term, year, marks, configs_qs)

        class_students = list(student.school_class.students.all())
        class_ranking = compute_report_card_ranking(class_students, term, year, included)

        stream_comparison = compute_stream_comparison(student.school_class.level_group, term, year, included)

        first_name = student.name.split(" ")[0]
        comments = {}
        term_record = student.term_records.filter(term=term, year=year).first()
        for role, field in (("classTeacher", "class_teacher_comment"), ("dos", "dos_comment"), ("hm", "hm_comment")):
            override = getattr(term_record, field, "") if term_record else ""
            if override:
                comments[role] = {"text": override, "is_override": True}
            else:
                comments[role] = {
                    "text": generate_role_comment(role, student.id, first_name, summary, trend, term, year),
                    "is_override": False,
                }

        return Response({
            "student": {
                "id": student.id, "name": student.name, "student_number": student.student_number,
                "class_name": student.school_class.name, "level": student.level, "combination": student.combination,
                "photo_url": student.photo_url,
            },
            "marks": [{"subject_id": m.subject_id, "subject_name": m.subject_name, "score": m.score, "grade": m.grade} for m in marks],
            "summary": {
                "mean_score": summary.mean_score, "mean_grade": summary.mean_grade, "mean_points": summary.mean_points,
                "result_band": summary.result_band, "result_label": summary.result_label,
            },
            "trend": {
                "has_previous_data": trend.has_previous_data, "direction": trend.direction,
                "previous_mean_score": trend.previous_mean_score, "current_mean_score": trend.current_mean_score,
                "delta": trend.delta,
            },
            "class_ranking": [
                {"student_id": r.student_id, "name": r.name, "student_number": r.student_number, "average": r.average, "combination": r.combination}
                for r in class_ranking
            ],
            "stream_comparison": [
                {"class_name": r.class_name, "stream": r.stream, "mean_score": r.mean_score, "student_count": r.student_count}
                for r in stream_comparison
            ],
            "comments": comments,
        })
