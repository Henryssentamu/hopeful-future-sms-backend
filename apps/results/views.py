from django.utils import timezone
from django.db import models, transaction
from django.shortcuts import get_object_or_404
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.academics.models import ReportCardConfig
from apps.accounts.models import Role
from apps.students.models import EnrollmentStatus, Student, TermEnrollment
from apps.notifications.services import notify_dos, notify_teacher

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


def _teacher_display_name(teacher):
    return teacher.user.get_full_name() or teacher.user.username


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

    def get_queryset(self):
        qs = self.queryset
        user = self.request.user
        if user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS):
            return qs
        teacher = getattr(user, "teacher_profile", None)
        if teacher:
            return qs.filter(
                models.Q(teacher=teacher) | models.Q(school_class__class_teacher=teacher)
            ).distinct()
        return qs.none()

    def create(self, request, *args, **kwargs):
        """POST /api/results/uploads/ — submitResultUpload(). Teacher-only,
        creates as PendingClassTeacher."""
        teacher = getattr(request.user, "teacher_profile", None)
        if not teacher:
            return Response({"detail": "Only teachers can submit results."}, status=403)
        serializer = SubmitResultUploadSerializer(data=request.data, context={"teacher": teacher, "enforce_window": True})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            upload = serializer.create_upload(teacher, ResultUploadStatus.PENDING_CLASS_TEACHER)
            class_teacher = upload.school_class.class_teacher
            if class_teacher and upload.school_class.class_teacher_id != teacher.id:
                notify_teacher(
                    class_teacher.user,
                    f"Results submitted for your review — {upload.school_class.name}",
                    f"{_teacher_display_name(teacher)} submitted {upload.entries.count()} {upload.result_type} results for "
                    f"{upload.subject.name} in your class. Please review and confirm or reject.",
                )
            elif class_teacher is None:
                notify_dos(
                    "New results submitted (no Class Teacher assigned)",
                    f"{_teacher_display_name(teacher)} submitted {upload.entries.count()} {upload.result_type} results for "
                    f"{upload.subject.name} — {upload.school_class.name}.",
                )
        return Response(ResultUploadSerializer(upload).data, status=201)

    @action(detail=True, methods=["post"])
    def resend(self, request, pk=None):
        """resendResultUpload() — submitting teacher only, only from a Rejected state."""
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=self.get_object().pk)
            if upload.status not in (ResultUploadStatus.REJECTED_BY_CLASS_TEACHER, ResultUploadStatus.REJECTED_BY_DOS):
                return Response({"detail": "Can only resend a rejected upload."}, status=400)
            if not IsSubmittingTeacherOfScope().has_object_permission(request, self, upload):
                return Response({"detail": "Only the submitting teacher may resend."}, status=403)
            serializer = ResendResultUploadSerializer(data=request.data, context={"upload": upload})
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
            class_teacher = upload.school_class.class_teacher
            if class_teacher:
                notify_teacher(
                    class_teacher.user,
                    f"Corrected results resent — {upload.school_class.name}",
                    f"{_teacher_display_name(upload.teacher)} corrected and resent {upload.result_type} results for {upload.subject.name}. Please review again.",
                )
        return Response(ResultUploadSerializer(upload).data)

    @action(detail=True, methods=["post"], url_path="class-teacher-confirm")
    def class_teacher_confirm(self, request, pk=None):
        """classTeacherConfirm() -> PendingDOS. No grade sync yet."""
        upload = self.get_object()
        if not IsClassTeacherOfScope().has_object_permission(request, self, upload):
            return Response({"detail": "Only this class's Class Teacher may confirm."}, status=403)
        if upload.status != ResultUploadStatus.PENDING_CLASS_TEACHER:
            return Response({"detail": "Upload is not awaiting Class Teacher review."}, status=400)
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=upload.pk)
            if upload.status != ResultUploadStatus.PENDING_CLASS_TEACHER:
                return Response({"detail": "Upload is not awaiting Class Teacher review."}, status=400)
            upload.status = ResultUploadStatus.PENDING_DOS
            upload.save(update_fields=["status"])
            notify_dos(
                "New results submitted",
                f"{_teacher_display_name(upload.school_class.class_teacher)} approved {upload.entries.count()} {upload.result_type} results for "
                f"{upload.subject.name} — {upload.school_class.name} (submitted by {_teacher_display_name(upload.teacher)}). Pending your review.",
            )
            if upload.teacher_id != upload.school_class.class_teacher_id:
                notify_teacher(
                    upload.teacher.user,
                    "Results approved by Class Teacher",
                    f"Your {upload.result_type} results for {upload.subject.name} — {upload.school_class.name} "
                    "were approved and forwarded to the Director of Studies.",
                )
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
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=upload.pk)
            if upload.status != ResultUploadStatus.PENDING_CLASS_TEACHER:
                return Response({"detail": "Upload is not awaiting Class Teacher review."}, status=400)
            upload.status = ResultUploadStatus.REJECTED_BY_CLASS_TEACHER
            upload.rejection_reason = serializer.validated_data["reason"]
            upload.rejected_by = RejectedBy.CLASS_TEACHER
            upload.rejected_by_name = request.user.get_full_name() or request.user.username
            upload.rejected_at = timezone.now()
            upload.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"])
            if upload.teacher_id != upload.school_class.class_teacher_id:
                notify_teacher(
                    upload.teacher.user,
                    "Results rejected — needs correction",
                    f"Your {upload.result_type} results for {upload.subject.name} — {upload.school_class.name} "
                    f"were rejected by your Class Teacher: \"{upload.rejection_reason}\"",
                )
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
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=upload.pk)
            if upload.status != ResultUploadStatus.PENDING_DOS:
                return Response({"detail": "Can only edit entries while awaiting DOS review."}, status=400)
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
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=upload.pk)
            if upload.status != ResultUploadStatus.PENDING_DOS:
                return Response({"detail": "Upload is not awaiting DOS review."}, status=400)
            upload.status = ResultUploadStatus.CONFIRMED
            upload.save(update_fields=["status"])
            apply_result_upload(upload)
            notify_teacher(
                upload.teacher.user,
                "Results confirmed",
                f"Your {upload.result_type} results for {upload.subject.name} — {upload.school_class.name} "
                "have been confirmed and are now reflecting on report cards.",
            )
            class_teacher = upload.school_class.class_teacher
            if class_teacher and class_teacher.id != upload.teacher_id:
                notify_teacher(
                    class_teacher.user,
                    f"Results confirmed — {upload.school_class.name}",
                    f"{upload.result_type} results for {upload.subject.name} in your class have been confirmed.",
                )
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
        with transaction.atomic():
            upload = ResultUpload.objects.select_for_update().get(pk=upload.pk)
            if upload.status != ResultUploadStatus.PENDING_DOS:
                return Response({"detail": "Upload is not awaiting DOS review."}, status=400)
            upload.status = ResultUploadStatus.REJECTED_BY_DOS
            upload.rejection_reason = serializer.validated_data["reason"]
            upload.rejected_by = RejectedBy.DOS
            upload.rejected_by_name = request.user.get_full_name() or request.user.username
            upload.rejected_at = timezone.now()
            upload.save(update_fields=["status", "rejection_reason", "rejected_by", "rejected_by_name", "rejected_at"])
            class_teacher = upload.school_class.class_teacher
            if class_teacher:
                notify_teacher(
                    class_teacher.user,
                    f"Results rejected by DOS — {upload.school_class.name}",
                    f"{upload.result_type} results for {upload.subject.name} (submitted by {_teacher_display_name(upload.teacher)}) "
                    f"were sent back by the Director of Studies: \"{upload.rejection_reason}\"",
                )
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

        serializer = SubmitResultUploadSerializer(data=request.data, context={"teacher": teacher, "enforce_window": False})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
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
        student = get_object_or_404(Student.objects.select_related("school_class"), pk=pk)
        term = request.query_params.get("term")
        try:
            year = int(request.query_params.get("year"))
        except (TypeError, ValueError):
            return Response({"year": "A valid year is required."}, status=400)

        enrollment = TermEnrollment.objects.select_related("school_class__class_teacher").filter(
            student=student, term=term, year=year, status=EnrollmentStatus.ENROLLED,
        ).first()
        if enrollment is None:
            return Response({"detail": "No term enrollment exists for this student and period."}, status=404)

        user = request.user
        teacher = getattr(user, "teacher_profile", None)
        allowed = user.is_superuser or user.role in (Role.ADMIN, Role.HEADMASTER, Role.DOS)
        if teacher:
            allowed = enrollment.school_class.class_teacher_id == teacher.id
        if not allowed:
            return Response({"detail": "You do not have access to this report card."}, status=403)

        configs_qs = ReportCardConfig.objects.all()
        included = get_included_result_types(configs_qs, term, year)

        historical_class = enrollment.school_class
        marks = compute_report_card_marks(student.id, historical_class.id, term, year, included)
        summary = compute_report_card_summary(marks)
        trend = compute_performance_trend(student.id, historical_class.id, term, year, marks, configs_qs)

        historical_student_ids = TermEnrollment.objects.filter(
            school_class=historical_class, term=term, year=year, status=EnrollmentStatus.ENROLLED,
        ).values_list("student_id", flat=True)
        class_students = list(Student.objects.filter(pk__in=historical_student_ids))
        class_ranking = compute_report_card_ranking(class_students, term, year, included)

        stream_comparison = compute_stream_comparison(historical_class.level_group, term, year, included)

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
                "class_name": historical_class.name, "level": enrollment.level, "combination": enrollment.combination,
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
