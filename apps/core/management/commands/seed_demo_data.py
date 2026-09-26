"""
Seeds the database with the exact dataset currently in the frontend's
src/data/mockData.ts. The JSON fixture at ./_seed_data/mockdata_export.json
was produced by bundling mockData.ts with esbuild and dumping every
exported array/constant to JSON (rather than hand-transcribing ~2800 lines
of literals by hand, which is what the original plan proposed but which
became impractical once the frontend's seed data grew to 37 students / 921
result uploads during this session) — the JS runtime is the ground truth
either way, and this guarantees byte-for-byte fidelity to it.

Order follows the app dependency chain (see plan doc): Users -> SchoolInfo/
AcademicPeriod -> Teachers/NonTeachingStaff -> Departments -> Subjects/
SubjectPapers -> SchoolClasses/ClassSubjectAssignments/TeacherAssignments ->
Students/ParentInfo/StudentSubjectEnrollments -> TermEnrollments ->
ResultUploads/ResultEntries -> REPLAY apply_result_upload against every one
of them -> Finance -> Requirements -> Recruitment -> Attendance.

Critical: TermSubjectMark / TermRecord.average / classPosition for Term 1
2025 (the term resultUploads covers) are NEVER hand-seeded from the
frontend's student.academicHistory literal — they are exclusively produced
by replaying the real apply_result_upload() engine against the seeded
ResultUploads, so seeded data and a live confirm-flow can never drift
apart. Older terms (Term 1-3 2024, etc.) have no corresponding
ResultUploads in the source data at all, so THOSE are hand-seeded directly
from academicHistory — there's nothing to replay them from, and doing so is
what lets compute_performance_trend's cross-term lookup be tested at all.
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role
from apps.academics.models import (
    AssignmentType,
    ClassSubjectAssignment,
    Department,
    ReportCardConfig,
    ResultWindow,
    SchoolClass,
    Subject,
    SubjectPaper,
    TeacherAssignment,
)
from apps.core.models import AcademicPeriod, Activity, SchoolInfo
from apps.finance.models import (
    ExpenditureCategory,
    ExpenditureRecord,
    FeeExtra,
    FeePayment,
    FeeStructure,
    IncomeRecord,
    SchoolRequirement,
    StudentFeeAssignment,
    StudentRequirementRecord,
)
from apps.finance.services import get_fee_structure
from apps.results.models import ResultEntry, ResultUpload
from apps.results.services import apply_result_upload, get_letter_grade
from apps.staff.models import BiometricLog, NonTeachingStaff, RecruitmentRecord, Teacher
from apps.students.models import (
    ParentInfo,
    Student,
    StudentAttendanceRecord,
    StudentSubjectEnrollment,
    TermEnrollment,
    TermRecord,
    TermSubjectMark,
)

User = get_user_model()
SEED_DATA_PATH = Path(__file__).parent / "_seed_data" / "mockdata_export.json"

# Models in FK-safe REVERSE dependency order, for --reset.
RESET_MODELS = [
    Activity,
    BiometricLog, StudentAttendanceRecord,
    StudentRequirementRecord, SchoolRequirement,
    IncomeRecord, ExpenditureRecord, ExpenditureCategory,
    FeePayment, StudentFeeAssignment, FeeExtra, FeeStructure,
    RecruitmentRecord,
    ResultEntry, ResultUpload,
    TermSubjectMark, TermRecord, TermEnrollment, StudentSubjectEnrollment, ParentInfo, Student,
    ResultWindow, ReportCardConfig, TeacherAssignment, ClassSubjectAssignment, SchoolClass,
    Department, SubjectPaper, Subject,
    NonTeachingStaff, Teacher,
    AcademicPeriod, SchoolInfo,
]

DEMO_ADMIN_ACCOUNTS = [
    ("admin", "System Administrator", Role.ADMIN),
    ("headmaster", "Head Master", Role.HEADMASTER),
    ("dos", "Director of Studies", Role.DOS),
    ("bursar", "Chief Bursar", Role.BURSAR),
    ("hr", "HR Officer", Role.HR),
]


class Command(BaseCommand):
    help = "Seed the database with the demo dataset ported from the frontend's mockData.ts."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete all seeded data first (FK-safe order).")

    def handle(self, *args, **options):
        if settings.IS_PRODUCTION:
            raise CommandError("Demo data seeding is disabled when DJANGO_ENVIRONMENT=production.")

        data = json.loads(SEED_DATA_PATH.read_text())

        if options["reset"]:
            self.stdout.write("Resetting existing data...")
            with transaction.atomic():
                for model in RESET_MODELS:
                    model.objects.all().delete()
                User.objects.filter(is_superuser=False).delete()

        with transaction.atomic():
            self._seed_admin_users()
            self._seed_school_info_and_period(data)
            teacher_by_name, teacher_by_fe_id = self._seed_teachers(data)
            nonteaching_by_fe_id = self._seed_non_teaching_staff(data)
            subject_by_name, paper_by_key = self._seed_subjects(data)
            self._seed_departments(data, subject_by_name, teacher_by_name)
            school_class_by_name = self._seed_school_classes(data, teacher_by_name, subject_by_name, paper_by_key, teacher_by_name)
            student_by_fe_id = self._seed_students(data, school_class_by_name, subject_by_name, paper_by_key)
            self._seed_term_enrollments(data, student_by_fe_id, school_class_by_name)
            self._seed_historical_term_records(data, student_by_fe_id)
            self._seed_result_uploads_and_replay(data, teacher_by_name, subject_by_name, paper_by_key, school_class_by_name, student_by_fe_id)
            self._seed_finance(data, student_by_fe_id)
            self._seed_requirements(data, student_by_fe_id)
            self._seed_recruitment(data)
            self._seed_student_attendance(data, student_by_fe_id, school_class_by_name)
            self._seed_staff_attendance(data, teacher_by_fe_id, nonteaching_by_fe_id)
            self._seed_activities()

        self._assert_counts()
        self.stdout.write(self.style.SUCCESS("Seed complete."))

    # ------------------------------------------------------------------
    def _unique_username(self, base: str) -> str:
        base = base.lower().replace(" ", ".").strip(".") or "user"
        username = base
        n = 1
        while User.objects.filter(username=username).exists():
            n += 1
            username = f"{base}{n}"
        return username

    def _seed_admin_users(self):
        from django.conf import settings

        for username, full_name, role in DEMO_ADMIN_ACCOUNTS:
            if User.objects.filter(username=username).exists():
                continue
            first, _, last = full_name.partition(" ")
            User.objects.create_user(
                username=username, email=f"{username}@hopefulfuture.test",
                first_name=first, last_name=last, role=role,
                password=settings.SEED_DEMO_PASSWORD,
            )

    def _seed_school_info_and_period(self, data):
        info = SchoolInfo.load()
        si = data["SCHOOL_INFO"]
        info.name = si["name"]
        info.short_name = si["shortName"]
        info.location = si["location"]
        info.po_box = si["poBox"]
        info.phone = si["phone"]
        info.email = si["email"]
        info.motto = si["motto"]
        info.save()

        period = AcademicPeriod.load()
        period.active_term = data["CURRENT_TERM"]
        period.active_year = data["CURRENT_YEAR"]
        period.save()

    def _seed_teachers(self, data):
        from django.conf import settings

        teacher_by_name, teacher_by_fe_id = {}, {}
        for t in data["teachers"]:
            first, _, last = t["name"].partition(" ")
            username = self._unique_username(t["email"].split("@")[0])
            user = User.objects.create_user(
                username=username, email=t["email"], first_name=first, last_name=last,
                role=Role.TEACHER, password=settings.SEED_DEMO_PASSWORD,
            )
            teacher = Teacher.objects.create(
                user=user, attendance=t["attendance"], performance=t["performance"],
                phone=t["phone"], status=t["status"], join_date=t["joinDate"],
            )
            teacher_by_name[t["name"]] = teacher
            teacher_by_fe_id[t["id"]] = teacher
        return teacher_by_name, teacher_by_fe_id

    def _seed_non_teaching_staff(self, data):
        from django.conf import settings

        nonteaching_by_fe_id = {}
        for s in data["nonTeachingStaff"]:
            first, _, last = s["name"].partition(" ")
            email = s.get("email") or f"{self._unique_username(first)}@hopefulfuture.test"
            username = self._unique_username(email.split("@")[0])
            user = User.objects.create_user(
                username=username, email=email, first_name=first, last_name=last,
                role=Role.NON_TEACHING, password=settings.SEED_DEMO_PASSWORD,
            )
            staff = NonTeachingStaff.objects.create(
                user=user, job_title=s["role"], department=s["department"],
                phone=s["phone"], join_date=s["joinDate"], status=s["status"],
            )
            nonteaching_by_fe_id[s["id"]] = staff
        return nonteaching_by_fe_id

    def _seed_subjects(self, data):
        subject_by_name, paper_by_key = {}, {}
        for s in data["subjects"]:
            subject = Subject.objects.create(
                subject_code=s["subjectCode"], name=s["name"],
                o_level_type=s["oLevelType"], a_level_type=s["aLevelType"],
                level=s["level"], status=s["status"],
                students_enrolled=s["studentsEnrolled"], description=s.get("description", ""),
            )
            subject_by_name[s["name"]] = subject
            for p in s.get("papers", []):
                paper = SubjectPaper.objects.create(subject=subject, paper=p["paper"], label=p["label"])
                paper_by_key[(s["name"], p["paper"])] = paper
        return subject_by_name, paper_by_key

    def _seed_departments(self, data, subject_by_name, teacher_by_name):
        for d in data["departments"]:
            head = teacher_by_name.get(d.get("headTeacherName")) if d.get("headTeacherName") else None
            dept = Department.objects.create(name=d["name"], head_teacher=head)
            dept.subjects.set([subject_by_name[n] for n in d["subjectNames"] if n in subject_by_name])

    def _seed_school_classes(self, data, teacher_by_name, subject_by_name, paper_by_key, _unused):
        school_class_by_name = {}
        for c in data["schoolClasses"]:
            class_teacher = teacher_by_name.get(c.get("classTeacher")) if c.get("classTeacher") else None
            school_class = SchoolClass.objects.create(
                name=c["name"], level_group=c["levelGroup"], stream=c["stream"],
                level=c["level"], class_teacher=class_teacher,
            )
            school_class_by_name[c["name"]] = school_class

            for subj_assignment in c.get("subjects", []):
                subject = subject_by_name.get(subj_assignment["subjectName"])
                if not subject:
                    continue
                assignment_type = (
                    AssignmentType.OPTIONAL if subj_assignment["type"] == "Elective" else AssignmentType.COMPULSORY
                )
                csa = ClassSubjectAssignment.objects.create(school_class=school_class, subject=subject, type=assignment_type)
                for ta in subj_assignment.get("teacherAssignments", []):
                    teacher = teacher_by_name.get(ta["teacherName"])
                    if not teacher:
                        continue
                    TeacherAssignment.objects.create(
                        class_subject_assignment=csa, teacher=teacher, papers=ta.get("papers", [])
                    )
        return school_class_by_name

    def _seed_students(self, data, school_class_by_name, subject_by_name, paper_by_key):
        student_by_fe_id = {}
        for s in data["students"]:
            school_class = school_class_by_name.get(s["class"])
            if not school_class:
                self.stderr.write(f"Skipping student {s['name']} — unknown class {s['class']!r}")
                continue
            student = Student.objects.create(
                student_number=s["studentNumber"], name=s["name"], school_class=school_class,
                combination=s.get("combination", "") or "", performance=s.get("performance", 0),
                email=s.get("email", "") or "", gender=s["gender"], age=s.get("age"),
                religion=s.get("religion", "") or "", location=s.get("location", "") or "",
                enrollment_date=s["enrollmentDate"], photo_url=s.get("photo", "") or "",
            )
            student_by_fe_id[s["id"]] = student

            if s.get("parentInfo"):
                p = s["parentInfo"]
                ParentInfo.objects.create(
                    student=student, father_name=p["fatherName"], mother_name=p["motherName"],
                    guardian=p.get("guardian", "") or "", phone=p["phone"], alt_phone=p.get("altPhone", "") or "",
                    email=p.get("email", "") or "", location=p["location"], district=p["district"],
                )

            for sub in s.get("subjects", []):
                subject = subject_by_name.get(sub["name"])
                if not subject:
                    continue
                paper = paper_by_key.get((sub["name"], sub["paper"])) if sub.get("paper") else None
                score = sub.get("score")
                grade = sub.get("grade") or (get_letter_grade(score) if score is not None else "")
                StudentSubjectEnrollment.objects.create(
                    student=student, subject=subject, paper=paper, type=sub["type"],
                    status=sub["status"], score=score, grade=grade,
                )
        return student_by_fe_id

    def _seed_term_enrollments(self, data, student_by_fe_id, school_class_by_name):
        for e in data["termEnrollments"]:
            student = student_by_fe_id.get(e["studentId"])
            school_class = school_class_by_name.get(e["className"])
            if not student or not school_class:
                continue
            TermEnrollment.objects.create(
                student=student, school_class=school_class, term=e["term"], year=e["year"],
                level=e["level"], combination=e.get("combination", "") or "",
                enrollment_date=e.get("enrollmentDate") or None, status=e["status"],
                notes=e.get("notes", "") or "",
            )

    def _seed_historical_term_records(self, data, student_by_fe_id):
        """
        Hand-seeds TermRecord/TermSubjectMark for every term in each
        student's academicHistory EXCEPT (Term 1, 2025) — that one is left
        for apply_result_upload to produce via replay (see module
        docstring). Older terms have no corresponding ResultUploads at all,
        so this is the only way to get that history in.
        """
        from apps.academics.models import Subject as SubjectModel

        current_term, current_year = data["CURRENT_TERM"], data["CURRENT_YEAR"]
        subject_by_name = {s.name: s for s in SubjectModel.objects.all()}

        for s in data["students"]:
            student = student_by_fe_id.get(s["id"])
            if not student:
                continue
            for record in s.get("academicHistory", []):
                if record["term"] == current_term and record["year"] == current_year:
                    continue
                term_record = TermRecord.objects.create(
                    student=student, term=record["term"], year=record["year"],
                    class_position=record.get("classPosition"), total_students=record.get("totalStudents"),
                    average=record.get("average"),
                    class_teacher_comment=record.get("classTeacherComment", "") or "",
                    dos_comment=record.get("dosComment", "") or "",
                    hm_comment=record.get("hmComment", "") or "",
                )
                for mark in record.get("marks", []):
                    subject = subject_by_name.get(mark["subject"])
                    if not subject:
                        continue
                    TermSubjectMark.objects.get_or_create(
                        term_record=term_record, subject=subject,
                        defaults={"score": mark["score"], "grade": mark["grade"]},
                    )

    def _seed_result_uploads_and_replay(self, data, teacher_by_name, subject_by_name, paper_by_key, school_class_by_name, student_by_fe_id):
        uploads_in_order = []
        for u in data["resultUploads"]:
            teacher = teacher_by_name.get(u["teacherName"])
            subject = subject_by_name.get(u["subject"])
            school_class = school_class_by_name.get(u["className"])
            if not (teacher and subject and school_class):
                self.stderr.write(f"Skipping resultUpload {u['id']} — unresolved teacher/subject/class")
                continue
            paper = paper_by_key.get((u["subject"], u["paper"])) if u.get("paper") else None

            upload = ResultUpload.objects.create(
                teacher=teacher, subject=subject, paper=paper, school_class=school_class,
                term=u["term"], year=u["year"], result_type=u["resultType"],
                weight_percent=u["weightPercent"], status=u["status"],
                rejection_reason=u.get("rejectionReason", "") or "",
                rejected_by=u.get("rejectedBy", "") or "",
                rejected_by_name=u.get("rejectedByName", "") or "",
                rejected_at=u.get("rejectedAt") or None,
            )
            ResultUpload.objects.filter(pk=upload.pk).update(upload_date=u["uploadDate"])

            entries = []
            for e in u["entries"]:
                student = student_by_fe_id.get(e["studentId"])
                if not student:
                    continue
                entries.append(ResultEntry(upload=upload, student=student, score=e["score"], grade=e["grade"]))
            ResultEntry.objects.bulk_create(entries)

            if upload.status == "Confirmed":
                uploads_in_order.append(upload)

        self.stdout.write(f"Replaying apply_result_upload for {len(uploads_in_order)} confirmed uploads...")
        for upload in uploads_in_order:
            apply_result_upload(upload)

    def _seed_finance(self, data, student_by_fe_id):
        fee_structure_map = {}
        for fs in data["feeStructures"]:
            structure = FeeStructure.objects.create(
                level_group=fs["className"], term=fs["term"], year=fs["year"], tuition=fs["tuition"],
            )
            fee_structure_map[(fs["className"], fs["term"], fs["year"])] = structure
            for extra in fs.get("extras", []):
                FeeExtra.objects.create(fee_structure=structure, name=extra["name"], amount=extra["amount"])

        for a in data["studentFeeAssignments"]:
            student = student_by_fe_id.get(a["studentId"])
            if not student:
                continue
            assignment = StudentFeeAssignment.objects.create(student=student, term=a["term"], year=a["year"])
            level_group = student.school_class.level_group
            structure = get_fee_structure(level_group, a["term"], a["year"])
            if structure and a.get("optedExtras"):
                extras = FeeExtra.objects.filter(fee_structure=structure, name__in=a["optedExtras"])
                assignment.opted_extras.set(extras)

        for p in data["feePayments"]:
            student = student_by_fe_id.get(p["studentId"])
            if not student:
                continue
            FeePayment.objects.create(
                student=student, term=p["term"], year=p["year"], amount=p["amount"],
                date=p["date"], method=p["method"], receipt_no=p["receiptNo"], notes=p.get("notes", "") or "",
            )

        category_by_fe_id = {}
        for c in data["expenditureCategories"]:
            category = ExpenditureCategory.objects.create(
                name=c["name"], group=c["group"], recurring=c["recurring"],
                recurring_period=c.get("recurringPeriod", "") or "",
                expected_amount=c.get("expectedAmount"), description=c.get("description", "") or "",
            )
            category_by_fe_id[c["id"]] = category

        for e in data["expenditures"]:
            category = category_by_fe_id.get(e["categoryId"])
            if not category:
                continue
            ExpenditureRecord.objects.create(
                category=category, item=e["item"], purpose=e["purpose"], amount=e["amount"],
                date=e["date"], paid_to=e.get("paidTo", "") or "", kind=e["kind"],
                period=e.get("period", "") or "", status=e["status"],
            )

        for i in data["incomes"]:
            if i["source"] == "School Fees":
                continue  # never stored — always computed from FeePayment
            student = student_by_fe_id.get(i.get("studentId")) if i.get("studentId") else None
            IncomeRecord.objects.create(
                source=i["source"], amount=i["amount"], date=i["date"],
                reference=i.get("reference", "") or "", description=i["description"],
                student=student, term=i.get("term", "") or "", year=i.get("year"),
            )

    def _seed_requirements(self, data, student_by_fe_id):
        requirement_by_fe_id = {}
        for r in data["schoolRequirements"]:
            applies_to_all = r["appliesTo"] == "All"
            requirement = SchoolRequirement.objects.create(
                name=r["name"], unit=r["unit"], quantity_required=r["quantityRequired"],
                term=r["term"], year=r["year"], applies_to_all=applies_to_all,
                applies_to_level_groups=[] if applies_to_all else r["appliesTo"],
                notes=r.get("notes", "") or "",
            )
            requirement_by_fe_id[r["id"]] = requirement

        for rec in data["studentRequirementRecords"]:
            student = student_by_fe_id.get(rec["studentId"])
            requirement = requirement_by_fe_id.get(rec["requirementId"])
            if not student or not requirement:
                continue
            StudentRequirementRecord.objects.create(
                student=student, requirement=requirement, quantity_brought=rec["quantityBrought"],
                date=rec.get("date") or None, notes=rec.get("notes", "") or "",
            )

    def _seed_recruitment(self, data):
        for r in data["recruitmentRecords"]:
            RecruitmentRecord.objects.create(
                candidate_name=r["candidateName"], staff_type=r["staffType"], role=r["role"],
                email=r.get("email", "") or "", phone=r["phone"], applied_date=r["appliedDate"],
                status=r["status"], notes=r.get("notes", "") or "",
            )

    def _seed_student_attendance(self, data, student_by_fe_id, school_class_by_name):
        for day in data["studentAttendance"]:
            school_class = school_class_by_name.get(day["className"])
            if not school_class:
                continue
            for mark in day["marks"]:
                student = student_by_fe_id.get(mark["studentId"])
                if not student:
                    continue
                StudentAttendanceRecord.objects.get_or_create(
                    student=student, date=day["date"],
                    defaults={"school_class": school_class, "status": mark["status"]},
                )

    def _seed_staff_attendance(self, data, teacher_by_fe_id, nonteaching_by_fe_id):
        for log in data["staffAttendance"]:
            if log["staffType"] == "Teaching":
                profile = teacher_by_fe_id.get(log["staffId"])
            else:
                profile = nonteaching_by_fe_id.get(log["staffId"])
            if not profile:
                continue
            BiometricLog.objects.create(
                staff=profile.user, date=log["date"],
                sign_in=log.get("signIn") or None, sign_out=log.get("signOut") or None,
            )

    def _seed_activities(self):
        """
        Dashboard "Recent Activity" feed — nothing in the app writes an
        Activity row yet (no signal/hook wires it up on confirm/payment/hire
        actions), so without this the endpoint would just be permanently
        empty. Rather than leave that empty state or fabricate events like
        the old mock did, this logs a handful of real rows drawn from data
        that's already been seeded above — genuine facts, not invented ones.
        `created_at` is auto_now_add so these will all show as "just seeded",
        which is honest: nothing has actually happened in this DB yet.
        """
        activities = []

        for u in ResultUpload.objects.filter(status="Confirmed").select_related("subject", "school_class").order_by("-id")[:6]:
            activities.append(Activity(
                message=f"{u.subject.name} {u.result_type} results confirmed for {u.school_class.name}",
                type="success",
            ))
        for u in ResultUpload.objects.exclude(rejected_by="").select_related("subject", "school_class").order_by("-id")[:3]:
            activities.append(Activity(
                message=f"{u.subject.name} results for {u.school_class.name} rejected by {u.rejected_by}",
                type="warning",
            ))
        for p in FeePayment.objects.select_related("student").order_by("-date")[:5]:
            activities.append(Activity(
                message=f"{p.student.name} paid UGX {p.amount:,} in {p.term} {p.year} fees",
                type="success",
            ))
        for r in RecruitmentRecord.objects.filter(status="Hired")[:3]:
            activities.append(Activity(message=f"{r.candidate_name} hired as {r.role}", type="info"))

        Activity.objects.bulk_create(activities)

    # ------------------------------------------------------------------
    def _assert_counts(self):
        expected = {
            Student: 37, Teacher: 12, Subject: 15, SchoolClass: 12, Department: 6,
            ResultUpload: 921, NonTeachingStaff: 7, RecruitmentRecord: 3,
        }
        problems = []
        for model, count in expected.items():
            actual = model.objects.count()
            if actual != count:
                problems.append(f"{model.__name__}: expected {count}, got {actual}")
        if problems:
            self.stderr.write(self.style.WARNING("Row-count mismatches:\n" + "\n".join(problems)))
        else:
            self.stdout.write(self.style.SUCCESS("Row counts match expected seed data."))
