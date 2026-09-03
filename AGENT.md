# Hopeful Future School Management System — Agent Guide

## Purpose and Required Use

This document is the authoritative orientation guide for anyone—or any coding agent—working on this backend. Read it completely before analyzing, implementing, reviewing, or updating the project.

Before making changes:

1. Inspect the current working tree and preserve unrelated user changes.
2. Read the files involved in the requested domain, including its models, serializers, views, services, URLs, migrations, and tests.
3. Treat backend permissions as the security boundary; client-side access controls are not a substitute.
4. Add or update migrations and tests when behavior or schema changes.
5. Do not silently change established enum strings or API response fields because clients rely on them.
6. If a backend change affects a shared API contract or user-visible behavior, read the frontend repository's `AGENTS.md` and complete `AGENT.md` before planning or implementing it.
7. After an approved change is implemented, update this guide—and the frontend guide only when the change crosses stack boundaries—to describe the new current behavior.

### Mandatory Python engineering standard

All Python changes must read like production code written and reviewed by an experienced senior backend engineer. This is a concrete maintainability requirement, not a request for decorative sophistication.

- Prefer the simplest design that fully enforces the business rule.
- Use precise domain names for modules, classes, functions, variables, fields, and tests.
- Keep functions focused, with obvious inputs, outputs, side effects, and transaction boundaries.
- Separate HTTP orchestration, validation, permissions, business workflows, and persistence concerns according to the project's existing architecture.
- Extract reusable behavior only when it represents a stable domain concept; do not introduce generic abstractions merely to reduce a few repeated lines.
- Use Django and DRF conventions before inventing custom frameworks or indirection.
- Make authorization and state transitions explicit at the point where they are enforced.
- Use type hints where they improve understanding, especially service inputs/outputs, without forcing noisy annotations onto self-evident Django code.
- Write short comments and docstrings only for business intent, invariants, non-obvious tradeoffs, or framework behavior. Do not narrate straightforward code.
- Avoid vague helpers, deeply nested branches, magic values, hidden mutations, broad exception handling, premature optimization, and clever one-liners.
- Preserve established project vocabulary and canonical data sources.
- Validate at the correct boundary and return predictable domain/API errors.
- Make multi-record workflows atomic and retry-safe where appropriate.
- Write behavior-focused tests with readable setup and meaningful names; cover success, invalid input, unauthorized access, state conflicts, and rollback behavior.
- Keep patches cohesive and reviewable. Do not mix unrelated cleanup or large stylistic rewrites into a feature change.
- Remove temporary debugging code and avoid placeholders, speculative abstractions, or generic boilerplate that does not serve the current requirement.

Before handing off Python code, reread it as a human maintainer: its purpose, control flow, invariants, and failure behavior should be understandable without reverse-engineering or relying on the original task conversation.

## Complete Product Description

Hopeful Future School Management System is a role-based digital operations platform for Hopeful Future Secondary School in Kayunga, Uganda. Its purpose is to give the school one authoritative system for the academic and administrative information that would otherwise be split across paper records, spreadsheets, disconnected browser state, and staff-specific workflows.

The system covers the lifecycle of the school's main people and processes:

- It authenticates administrators, the Headmaster, Director of Studies (DOS), Bursar, Human Resources staff, teachers, and non-teaching staff and gives each role the appropriate working area.
- It stores the school's identity and maintains a single active academic term and year shared by all users.
- It organizes subjects, subject papers, departments, classes/streams, class teachers, subject allocations, and teacher responsibilities.
- It maintains student biodata, parent/guardian information, current class membership, historical term enrollment, subject enrollment, and daily attendance.
- It supports a governed assessment workflow in which teachers enter results, class teachers review them, the DOS reviews or corrects them, and confirmed results update marks, averages, rankings, trends, and report cards.
- It generates report-card information from confirmed assessment evidence and supports role-specific comments from the class teacher, DOS, and Headmaster.
- It manages fee structures, optional charges, payments, balances, income, expenditure, school requirements, and previous-term obligations.
- It records staff recruitment and hiring, teacher/non-teaching profiles, generated login credentials, password resets, and biometric attendance.
- It provides manual timetable construction with teacher, room, and class conflict detection.
- It delivers role-scoped notifications and a dashboard activity feed.

This backend is the system of record and security boundary. The frontend presents role-appropriate workflows and must remain aligned with backend models, validation, permissions, workflow states, and response contracts. A feature is not complete merely because one stack compiles: stored data, API behavior, frontend interaction, permissions, user feedback, and documentation must describe the same behavior.

### Intended users and responsibilities

- **Administrator:** broad system access, configuration, and operational oversight.
- **Headmaster:** broad school oversight, report-card configuration/comments, and access equivalent to Administrator where the backend allows Administrator.
- **Director of Studies:** academic structures, students, timetables, result windows, result review/confirmation, and DOS comments.
- **Bursar:** fees, payments, income, expenditure, requirements, and financial monitoring.
- **Human Resources:** teaching/non-teaching staff, recruitment, hiring, attendance, and credential resets.
- **Teacher:** assigned-class/subject result submission and, when appointed as a class teacher, class review, attendance, performance, and comments.
- **Non-teaching staff:** authenticated access to the limited staff portal intended for their role.

### System boundaries

The current project does not yet provide a student/parent self-service portal, payroll, library management, boarding/dormitory management, inventory procurement, automatic timetable generation, online payment-provider integration, immutable accounting ledger, or production-ready messaging delivery. Do not assume these exist; treat them as new features requiring explicit product and cross-stack design.

## Related Frontend and Cross-Stack Documentation Rule

The corresponding frontend is normally located at:

`/home/henry/projects/schoolManagmentSystems/frontends/hopeful-future-portal`

This backend guide does not duplicate the frontend's architecture, technology stack, UI/UX rules, pages, or component details. Those belong to the frontend guide.

Before implementing or approving a backend change that affects an API contract or user-visible behavior, agents must read:

1. This backend `AGENTS.md` and complete `AGENT.md`.
2. The frontend `AGENTS.md`.
3. The complete frontend `AGENT.md`.
4. The relevant frontend source and tests identified by that guide.

“Frontend impact” includes more than visual changes. It includes endpoint paths or methods, request/response fields, enum values, pagination, filtering, ordering, permissions, authentication/session behavior, error shapes, workflow states, defaults, nullable fields, date/time formats, computed values, loading behavior, and any capability exposed or removed by a backend change.

For an approved cross-stack change:

- Update the backend implementation, migrations, tests, schema, and this backend guide as applicable.
- Update or explicitly coordinate the frontend implementation, tests, and frontend guide as applicable.
- If only one repository is authorized for editing, document the required companion-stack change and do not claim end-to-end completion.
- Never push or hand off a contract-changing backend update while knowingly leaving the frontend contract incompatible.
- Record durable architectural decisions and newly discovered limitations in the relevant guide; do not fill the guide with temporary task logs or speculative plans.

## Architecture Summary

The backend is a modular Django monolith: separate Django applications share one Django process, one relational database, and a common REST API.

Typical request flow:

```text
Django URL/router
    -> DRF view or viewset
    -> serializer validation
    -> service-layer business logic where applicable
    -> Django ORM
    -> MySQL
```

Redis is configured for Django caching and as the Celery broker/result backend. Celery is currently scaffolding: eager execution is enabled by default, Docker Compose does not start a worker, and result processing is synchronous.

## Technology Stack

### Backend

- Python 3.12
- Django 5.0
- Django REST Framework 3.15
- djangorestframework-simplejwt
- django-filter
- drf-spectacular/OpenAPI
- MySQL 8 with `mysqlclient` in Docker
- PyMySQL fallback for local development
- Redis 7 and `django-redis`
- Celery 5.4
- Docker and Docker Compose
- `python-dotenv` for environment configuration

## Repository Layout

```text
apps/
  accounts/       users, roles, JWT authentication, permissions
  core/           school singleton data, active period, activity feed, seed command
  staff/          teachers, non-teaching staff, recruitment, biometric logs
  academics/      subjects, papers, departments, classes, assignments, result windows
  students/       students, parents, enrollment, attendance, historical term records
  results/        upload/review workflow, grading, ranking, report cards
  finance/        fees, payments, income, expenditure, school requirements
  timetable/      configurations, periods, slots, conflict detection
  notifications/  recipient- and role-scoped notifications
config/
  settings.py     Django, database, REST, JWT, Redis, Celery, CORS configuration
  urls.py         top-level API routes and schema documentation
  celery.py       Celery application initialization
Dockerfile
docker-compose.yml
requirements.txt
requirements-local.txt
manage.py
```

Each domain generally follows this separation:

- `models.py`: schema, persistent invariants, relationships, and enums.
- `serializers.py`: API representation and request validation.
- `views.py`: authorization, HTTP orchestration, and endpoints.
- `services.py`: reusable or multi-model business operations.
- `urls.py`: routers and custom paths.
- `admin.py`: Django admin registration.
- `migrations/`: committed schema history.
- `tests.py` or `tests/`: automated tests.

Keep multi-model workflows and calculations in services rather than duplicating them in views or serializers.

## Configuration and Runtime

The main configuration is `config/settings.py`.

- Custom user model: `accounts.User`.
- Default API authentication: JWT.
- Default permission: authenticated users only.
- Default pagination: page-number pagination, 50 records per page.
- Filtering: DjangoFilterBackend, search, and ordering.
- API schema: `/api/schema/`.
- Swagger UI: `/api/docs/`.
- Time zone: `Africa/Kampala`.
- Database: MySQL only; there is no SQLite fallback.
- Default frontend CORS origin: `http://localhost:8080`.
- Redis logical database 1 is used for cache; database 0 is used for Celery.
- Media is served by Django only while `DEBUG` is enabled.

Environment variables are documented in `.env.example`. Never expose or commit real `.env` contents.

Docker Compose defines MySQL, Redis, and the Django development server. It maps MySQL to host port 3307 and Redis to 6380 while containers communicate internally on their default ports. The web container currently runs Django's development server, not a production WSGI/ASGI server.

## Authentication and Authorization

### Roles

The role enum in `apps/accounts/models.py` contains:

- `ADMIN`
- `HEADMASTER`
- `DOS`
- `BURSAR`
- `HR`
- `TEACHER`
- `NON_TEACHING`

Every login-capable person is an `accounts.User`. Teachers and non-teaching staff have one-to-one profile models in `apps.staff`.

JWT endpoints:

- `POST /api/auth/login/`
- `POST /api/auth/refresh/`
- `GET /api/auth/me/`

Login returns `access`, `refresh`, and a serialized `user`. JWT access tokens also contain role and display-name claims.

The permission base class treats Headmaster as having the same full-system access as Administrator wherever Administrator is allowed. Superusers bypass role checks.

When implementing endpoints:

- Enforce role and object scope in the backend.
- Do not rely on client-side route or visibility controls.
- Distinguish collection-level permission checks from object-level checks.
- Restrict sensitive reads, not only writes.
- Return controlled `400`, `403`, and `404` responses for invalid input and scope violations.

## Detailed Application Reference

The following sections describe what each Django app owns, how its files cooperate, which other apps it depends on, and how it contributes to the complete product. Agents must still inspect the live files before changing them; this is an architectural map, not permission to work from memory.

### `apps.accounts` — identity, sessions, and authorization vocabulary

**Purpose and contribution:** Accounts establishes who a caller is and the broad role under which they operate. Every protected domain depends on its authentication and permission vocabulary, making it the foundation of the security model.

**Models (`models.py`):**

- `Role` is the shared role enum: Administrator, Headmaster, DOS, Bursar, HR, Teacher, and Non-Teaching.
- `User` extends Django `AbstractUser` with a required `role`. It remains canonical for username, password hash, email, first/last name, active/staff flags, and Django authorization fields.
- Teacher- and non-teaching-specific attributes do not belong on `User`; they live in `apps.staff` one-to-one profiles.

**Serializers (`serializers.py`):**

- `UserSerializer` is read-only and exposes identity, role, and nullable `teacher_id`/`non_teaching_staff_id` links for frontend routing.
- `LoginSerializer` extends SimpleJWT, adds role/name claims to tokens, and returns serialized user data alongside the access/refresh pair.

**Views and routes (`views.py`, `urls.py`):**

- `LoginView` handles credential authentication at `POST /api/auth/login/`.
- SimpleJWT's refresh view is mounted at `POST /api/auth/refresh/`.
- `MeView` returns the authenticated user at `GET /api/auth/me/`.

**Permissions (`permissions.py`):**

- `HasRole` is the reusable base for role-only access.
- Specialized classes cover Admin, Headmaster, DOS, Bursar, HR, Teacher, and admin-side combinations.
- A superuser always passes. Where Admin is permitted, `HasRole` implicitly also permits Headmaster.
- Object/scope permissions involving classes or teacher allocations belong in the domain that owns those relationships, such as `apps.results.permissions`.

**Cross-app connections:** `staff.Teacher` and `staff.NonTeachingStaff` attach to User; activities, notifications, biometric logs, and result ownership reference users or their profiles. All DRF endpoints inherit authenticated-by-default behavior from settings.

**Change cautions:** Changing role strings, token/user response fields, or Headmaster/Admin equivalence changes a shared contract and requires cross-stack coordination.

### `apps.core` — institution-wide settings, audit-style feed, and demo bootstrap

**Purpose and contribution:** Core owns school-wide configuration used across domains and the import path that turns the original frontend demonstration dataset into relational backend data.

**Models (`models.py`):**

- `FinanceTerm` defines the shared `Term 1`/`Term 2`/`Term 3` vocabulary used by academics, students, results, and finance.
- `ResultType` defines Beginning of Term, Test, Midterm, Project, and End of Term categories.
- `SingletonModel` forces singleton configuration rows to primary key 1, supplies `load()`, and disables deletion.
- `SchoolInfo` stores official school identity/contact/motto data used by the UI and printed documents.
- `AcademicPeriod` stores the one active term/year shared across all users.
- `Activity` stores a timestamped informational/success/warning dashboard entry and optional User actor.

**Serializers:** `SchoolInfoSerializer` and `AcademicPeriodSerializer` expose editable singleton fields; `ActivitySerializer` is read-only and adds the actor's display name.

**Views and routes:**

- `/api/core/school-info/`: authenticated GET, Admin/Headmaster PATCH through `IsAdmin` semantics.
- `/api/core/academic-period/`: authenticated GET, Admin/Headmaster PATCH.
- `/api/core/activities/`: authenticated list of the most recent 50 activities.

**Services:** `get_previous_term()` maps a term/year to the preceding period and is consumed by finance balances and result trends.

**Management command:** `seed_demo_data` reads `_seed_data/mockdata_export.json`, creates records in foreign-key order, replays current result uploads through the real result engine, imports historical marks where source uploads do not exist, and can destructively reset application data with `--reset`.

**Cross-app connections:** Core enums are imported by academics/results/students/finance. `AcademicPeriod` is exposed as the shared period for API clients. The seed command depends on nearly every domain app. `Activity` links to accounts, though normal business services currently create few/no ongoing activity entries beyond seed data.

**Change cautions:** Term/result-type strings are cross-stack contracts. Singleton mutation affects all users. Seed changes must remain idempotent enough for intended usage, preserve dependency order, and never be run with `--reset` against unverified data.

### `apps.staff` — workforce profiles, recruitment, credentials, and attendance

**Purpose and contribution:** Staff represents employees after authentication, manages hiring candidates into real accounts, and records staff attendance. Academics and results rely on teacher profiles rather than generic users.

**Models:**

- `Teacher` is a one-to-one User profile containing attendance/performance percentages, phone, status, and join date.
- `NonTeachingStaff` is a one-to-one User profile containing job title, department, phone, join date, and employment status.
- `RecruitmentRecord` stores a candidate, intended staff type/job role, contact details, application date, decision state, and notes.
- `BiometricLog` belongs directly to a User, permits one record per staff/date, holds sign-in/out times, and calculates same-day hours.
- Enums define teacher presence status, employment status, staff type, and recruitment state.

**Serializers:** Teacher and non-teaching serializers nest read-only User data and derive name/email. Recruitment validation prevents setting `Hired` through generic PATCH. Biometric serialization adds staff name, role, and calculated hours.

**Views and routes:**

- `/api/staff/teachers/`: authenticated reads; HR/Admin/Headmaster writes; `roles/` derives academic responsibilities; `reset-password/` returns a generated password once.
- `/api/staff/non-teaching/`: similar reads/writes and password reset.
- `/api/staff/recruitment/`: HR/Admin/Headmaster CRUD and dedicated `hire/` action.
- `/api/staff/biometric-logs/`: admin-side staff CRUD with staff/date filters.

**Services:** `hire_candidate()` creates a unique username, generated password, User, correct profile type, and hired status inside a transaction. `reset_password()` replaces a password and returns the generated value. Academic teacher-role derivation is intentionally delegated to `academics.services`.

**Cross-app connections:** Accounts supplies User/Role. Academics references Teacher for class teachers, department heads, and teaching assignments. Results references Teacher as upload owner. Timetable references Teacher for scheduling. BiometricLog can reference any staff User.

**Change cautions:** Generated passwords are sensitive and one-time. Hiring needs stronger already-hired/concurrency protection. Teacher serializer creation is not a general account-creation path because User is read-only. Cached attendance/performance fields need an explicit source-of-truth policy if automated calculations are added.

### `apps.academics` — curriculum, school structure, teaching allocation, and assessment configuration

**Purpose and contribution:** Academics describes what the school teaches, how learners are grouped, who teaches each class/subject/paper, and which assessment periods/configurations govern results.

**Models:**

- `Subject` stores code, unique name, O-/A-Level applicability/type, status, cached enrollment count, and description.
- `SubjectPaper` normalizes papers belonging to a subject and is unique per subject/paper code.
- `Department` groups subjects and optionally assigns a Teacher as head.
- `SchoolClass` is an actual stream/class with level group, stream, education level, and optional class teacher.
- `ClassSubjectAssignment` states that a subject is taught in a class and whether it is compulsory or optional.
- `TeacherAssignment` assigns a Teacher to that class-subject relationship and stores the paper labels they cover.
- `ReportCardConfig` selects included result types for one term/year.
- `ResultWindow` defines opening and closing timestamps for one result type/term/year.
- Enums define education levels, subject applicability/type/status, level groups, and compulsory/optional assignment types.

**Serializers:** Subject responses nest papers. Department responses expose IDs plus subject/head-teacher names. Class-subject responses nest teacher assignments, and class responses nest their full subject/teacher allocation. Dedicated serializers validate assign/remove-teacher action payloads. Report-card and result-window serializers expose their configurations.

**Views and routes:** Model viewsets expose subjects, subject papers, departments, classes, class-subject assignments, report-card configurations, and result windows under `/api/academics/`. Authenticated users generally read; DOS/Admin/Headmaster manage academic structures, while report-card configuration is Headmaster/Admin-managed. Class actions assign or remove teachers.

**Services:**

- `assign_teacher_to_class_subject()` creates/updates the class-subject and merges paper responsibility idempotently.
- `remove_teacher_from_class_subject()` removes a teacher's complete assignment for that subject/class.
- Role helpers derive subject-teacher, class-teacher, and department-head responsibilities rather than storing duplicate labels.

**Cross-app connections:** Teacher references come from staff. Students belong to SchoolClass and enroll in Subjects/Papers. ResultUpload scopes are built from class, subject, and paper. Finance uses `level_group` for fees/requirements. Timetable slots use classes, subjects, and teachers.

**Change cautions:** Validate that paper labels belong to the chosen subject and teacher allocation. Deleting protected curriculum records may affect students/results. ResultWindow currently is not enforced by result submission. `students_enrolled` is cached and can drift unless its update policy is centralized.

### `apps.students` — learner records, guardians, enrollment history, attendance, and stored academic summaries

**Purpose and contribution:** Students is the hub for learner identity and longitudinal enrollment. It connects the academic structure to results, attendance, finance, and report cards.

**Models:**

- `Student` stores student number, name, current SchoolClass, A-Level combination, cached performance, contact/demographic details, enrollment date, and optional photo URL. `level` is derived from the class.
- `ParentInfo` is the student's one-to-one parent/guardian and contact record.
- `StudentSubjectEnrollment` stores current subject/paper enrollment status plus latest calculated paper score/grade.
- `TermEnrollment` snapshots the student's actual class, level, combination, date, status, and notes for one term/year.
- `TermRecord` stores the term average, class position/population, and manual class-teacher/DOS/Headmaster comment overrides.
- `TermSubjectMark` stores one subject-level score/grade per TermRecord.
- `StudentAttendanceRecord` stores one present/absent mark per student/date and the class context.

**Serializers:** Student responses include class/level, nested parent data, and nested subject enrollments; performance is read-only. Enrollment serializers add readable class/subject/paper names. TermRecord nests read-only marks and calculated summary fields. `UpdateCommentSerializer` restricts editable role keys and comment length.

**Views and routes:**

- `/api/students/`: authenticated reads and DOS/Admin/Headmaster writes, with class/gender filters and name/number search.
- Student detail action `/term-records/{term}/{year}/comment/` authorizes the requested comment role, using historical TermEnrollment for class-teacher ownership.
- `/parent-info/`, `/subject-enrollments/`, `/term-enrollments/`, and `/term-records/` provide related CRUD with academic-management permissions.
- `/attendance/` supports authenticated admin-side/class-teacher writes under its current permission rules.
- Report-card retrieval is implemented by `apps.results.ReportCardView` but mounted below the student URL namespace.

**Services:** `is_enrolled_for_term()` and `get_enrollment()` provide canonical term-enrollment lookups used by finance and historical workflows.

**Cross-app connections:** SchoolClass, Subject, SubjectPaper, and AssignmentType come from academics. Result entries point to Student and confirmation updates student academic records. Finance models reference Student throughout. Historical enrollment determines report trends and comment authorization.

**Change cautions:** Student/guardian data is personally sensitive. Current read scope is broad. Keep current versus historical class concepts separate. MySQL permits duplicate paperless enrollment rows despite the nullable-paper unique constraint; service-level upsert protection remains necessary. Do not write cached performance independently of the result engine without defining reconciliation.

### `apps.results` — governed assessment workflow and report-card computation

**Purpose and contribution:** Results converts raw teacher-entered assessment scores into reviewed, authoritative academic records and live report-card analytics. It is the most business-critical multi-model workflow.

**Models:**

- `ResultUpload` represents one teacher/subject/optional-paper/class/term/year/result-type submission with a weight and workflow/rejection metadata.
- `ResultEntry` stores one student's score and derived grade within an upload and is unique per upload/student.
- `ResultUploadStatus` defines class-teacher review, DOS review, both rejection states, and confirmed.
- `RejectedBy` records reviewer category.

**Serializers:** `ResultUploadSerializer` returns readable teacher/subject/class names and nested entries. `EntryInputSerializer` restricts scores to 0–100. Submission, resend, rejection, and DOS-entry-edit serializers describe action-specific payloads. Submission currently uses raw ID fields and needs stronger cross-model/domain validation.

**Permissions:** `IsDOSOrAdmin` includes Headmaster. `IsSubmittingTeacherOfScope` verifies upload ownership plus teacher allocation. `IsClassTeacherOfScope` verifies the upload class's current class teacher.

**Views and routes:** `/api/results/uploads/` supports authenticated list/retrieve and action-only mutation: create submission, resend, class-teacher confirm/reject, DOS edit-entry, confirm, DOS reject, enter-and-confirm, and missing-marks. Generic update/delete is disabled. `ReportCardView`, mounted as `/api/students/{id}/report-card/`, returns the full report-card bundle.

**Services:**

- Grading helpers calculate letter grades, points, bands, tiers, remarks, and weighted averages.
- `get_included_result_types()` applies ReportCardConfig with all-types fallback.
- `apply_result_upload()` synchronizes confirmed evidence into paper enrollments, subject marks, term averages, cached student performance, and rankings.
- Report-card helpers compute marks, summaries, ranking, historical trend, and stream comparison.
- Deterministic comment helpers generate role-appropriate comments and preserve frontend-compatible selection behavior.
- `find_missing_marks()` determines expected students based on O-Level compulsory rules or active subject/paper enrollment.

**Cross-app connections:** Accounts supplies reviewer roles; staff supplies submitting teachers; academics supplies scope/configuration; students receives entries and derived academic records; core supplies result/term enums and previous-period calculation. Notification services exist but are not currently wired into workflow transitions.

**Change cautions:** Keep transitions atomic, authorized, state-checked, and ideally idempotent. Initial submission must be hardened for assignment, paper, class/student, duplicates, enum, weight, and ResultWindow validation. Report-card calculations can be query-heavy. Historical calculations must use TermEnrollment rather than blindly using current class. Any grade/workflow/response change requires coordinated frontend updates.

### `apps.finance` — fees, receipts, income, expenditure, and material requirements

**Purpose and contribution:** Finance gives the Bursar and school leadership a view of student obligations, received funds, spending, non-fee income, required items, and period summaries.

**Models:**

- `FeeStructure` defines tuition by level group/term/year; `FeeExtra` defines optional attached charges.
- `StudentFeeAssignment` records a student's opted extras for a term/year.
- `FeePayment` records amount, date, method, unique receipt, and notes.
- `ExpenditureCategory` describes grouped recurring/one-off spending expectations.
- `ExpenditureRecord` records actual spending, payee, kind, free-text period, and status.
- `IncomeRecord` stores non-fee income and rejects `School Fees`, because fee income is derived from FeePayment.
- `SchoolRequirement` defines required physical items and applicable level groups.
- `StudentRequirementRecord` records quantities brought by a student.
- Enums define payment state/method, income source, expenditure kind/group/period, and requirement state.

**Serializers:** Resource serializers expose nested fee extras or readable student/category names where needed. Income validation duplicates the model-level protection against storing school-fee income.

**Views and routes:** CRUD viewsets live under `/api/finance/`; authenticated users currently read, while Bursar/Admin/Headmaster write. Computed endpoints return student fee status, student requirement status, and income/expenditure overview with term/year and optional filters.

**Services:** Helpers parse free-text periods, locate fee structures, calculate total due and paid, classify payment/requirement status, and total fee income. Core previous-term logic supplies outstanding balances. Student term-enrollment services indicate whether a student is enrolled for the selected period.

**Cross-app connections:** Finance references Student and academic LevelGroup, uses core term values and period helpers, and exposes CRUD plus computed reporting endpoints to authorized clients.

**Change cautions:** Financial reads are currently broadly available to authenticated users. Preserve FeePayment as the only source of fee-income totals. Free-text expenditure period parsing is fragile. Important finance mutations need audit/reversal/reconciliation design. Avoid floating point for money; current positive integer UGX convention is deliberate.

### `apps.timetable` — schedule structure and conflict-safe manual allocation

**Purpose and contribution:** Timetable lets academic administrators define a schedule grid and manually allocate lessons while receiving conflicts for teachers, rooms, and classes.

**Models:**

- `TimetableConfig` owns a named schedule with JSON lists of days and rooms.
- `TimetablePeriod` defines ordered start/end times and optional breaks within a configuration.
- `TimetableSlot` assigns an optional subject, paper label, Teacher, SchoolClass, and room to a day/period or represents a break.

**Serializers:** Period and slot serializers expose nested readable names. `TimetableSlotSerializer.validate()` resolves full or partial-update values and asks the conflict service to reject colliding allocations. Config responses nest periods and slots.

**Views and routes:** `/api/timetable/configs/`, `/periods/`, and `/slots/` provide ModelViewSet CRUD. Authenticated users read; DOS/Admin/Headmaster write. Periods filter by config, while slots filter by config/day/teacher/class/room.

**Services:** `find_conflicts()` searches a single config/day/period and reports teacher, room, and class collisions, excluding the slot being edited.

**Cross-app connections:** Subjects and SchoolClasses come from academics; Teacher comes from staff; timetable APIs expose the constructed schedule to clients.

**Change cautions:** There is no automatic generation algorithm. Validate that days/period indexes/rooms belong to the selected config and that lesson/break field combinations are coherent. Application-level conflict checking can race without database/transaction protection. Treat slot field changes as shared API-contract changes.

### `apps.notifications` — role-scoped and user-scoped in-app messages

**Purpose and contribution:** Notifications communicates workflow or administrative information to the DOS, all teachers, or a specific user and exposes unread/read state to the portal.

**Models:** `Notification` stores optional recipient, broadcast scope, title, message, created timestamp, and one shared `read` flag. `BroadcastScope` defines DOS, all-teachers, and specific-user audiences.

**Serializers:** `NotificationSerializer` exposes all fields and makes only creation time read-only. It does not currently enforce the relationship between scope and whether recipient must be set.

**Views and routes:** `NotificationViewSet` at `/api/notifications/` filters records to the current user, teacher broadcasts, or DOS broadcasts as applicable. It provides `mark-read` and `mark-all-read` actions but also inherits generic ModelViewSet creation/update/deletion.

**Services:** `notify_dos()`, `notify_teacher()`, and `notify_all_teachers()` provide small creation helpers intended for domain workflows, though result/staff workflows do not currently call them.

**Cross-app connections:** Notification recipients are accounts.Users. Results and other workflow apps are expected future producers; authenticated API clients are consumers.

**Change cautions:** Any authenticated caller can currently create generic notifications, and read state on a broadcast row is shared—one teacher marking a broadcast read can effectively mark the same record read for all teachers. A per-user delivery/read model is preferable. Restrict mutation permissions and validate scope-recipient consistency before production use.

## Cross-App Dependency and Data-Flow Map

The practical dependency direction is:

```text
accounts
   ├── core (activity actor)
   ├── staff (employee profiles and biometric users)
   └── notifications (recipients)

core term/result vocabularies
   ├── academics
   ├── students
   ├── results
   └── finance

staff.Teacher
   ├── academics assignments/class leadership
   ├── results upload ownership/review scope
   └── timetable scheduling

academics classes/subjects/papers
   ├── students enrollment/history
   ├── results scope/configuration
   ├── finance level-group rules
   └── timetable slots

students
   ├── results entries and calculated records
   └── finance payments/requirements
```

Important end-to-end flows:

- **Login:** API client credentials -> accounts login serializer -> JWT and serialized User -> authenticated role-aware client session.
- **Academic configuration:** DOS/HM/Admin UI -> academics/core endpoints -> shared relational structures and active period -> all consuming hooks/pages.
- **Results:** teacher allocation -> student/class scope -> upload/entries -> class-teacher review -> DOS confirmation -> derived student records -> report-card endpoint -> printable UI.
- **Finance:** class level group + fee structure/extras + student assignment + payments -> computed balance/status -> Bursar/Accounts UI and overview.
- **Hiring:** HR candidate -> staff hire service -> accounts.User + staff profile -> generated credentials -> staff/teacher portals and future allocations.
- **Timetable:** academic classes/subjects + staff teachers + config periods/rooms -> slot validation -> schedule API representation.
- **Notifications:** domain service creates audience message -> filtered API queryset -> client list/read actions.

## Domain Model and Interactions

### Accounts

`accounts.User` extends Django's `AbstractUser` with a required role. `UserSerializer` exposes profile IDs so the frontend can route teachers and non-teaching staff to their own portals without matching by name.

### Core

`SchoolInfo` and `AcademicPeriod` derive from `SingletonModel`; they always use primary key 1 and cannot be deleted through the model API.

`AcademicPeriod` is the shared server-side active term/year. It replaced a browser-local value, ensuring all users see the same period.

`Activity` is the dashboard feed and holds a message, severity-like type, optional actor, and timestamp.

### Staff

`Teacher` and `NonTeachingStaff` point one-to-one to `User`. Names and emails remain canonical on the user record.

Recruitment uses a dedicated service. Hiring a candidate creates a user and the appropriate profile, generates a one-time password, and marks the recruitment record as hired inside a transaction.

Biometric logs record one sign-in/sign-out pair per staff user per date. Calculated hours clamp negative intervals to zero and do not support overnight shifts.

### Academics

Subjects can apply to O-Level, A-Level, or both and may have normalized `SubjectPaper` children.

`SchoolClass` represents a real stream, such as Senior 2 A. `level_group` is only a reporting/fee grouping; students enroll in actual classes.

Teaching allocation is normalized:

```text
SchoolClass + Subject
    -> ClassSubjectAssignment
    -> one or more TeacherAssignments
    -> selected paper labels
```

Do not reintroduce duplicated teacher/class/subject arrays on Teacher or Subject.

`ReportCardConfig` controls assessment categories included in report cards for a term/year. Absence of a configuration means all result types count.

`ResultWindow` stores opening and closing timestamps for a result category, term, and year. Current submission code does not enforce these timestamps; this is a known gap.

### Students

`Student` belongs to a current `SchoolClass`; level is derived from that class. `ParentInfo` is one-to-one.

`TermEnrollment` is the historical record of the student's actual class and enrollment status for a term/year. Use it when resolving historical class ownership or report context; do not assume the current class was always the historical class.

`StudentSubjectEnrollment` stores the current paper-level score and enrollment status. `TermSubjectMark` stores a term's subject-level result. `TermRecord` stores average, rank, population, and optional manual role comments.

Student attendance is normalized to one student/date row.

### Results

Results implement a state machine:

```text
Teacher submission
    -> PendingClassTeacher
    -> PendingDOS
    -> Confirmed
```

Reviewers may instead transition to `RejectedByClassTeacher` or `RejectedByDOS`; the submitting teacher may correct and resend a rejected upload. DOS/Admin/Headmaster can use a fast path to enter and confirm results directly.

Final confirmation calls `apply_result_upload()`, which:

1. Finds all confirmed contributions for the subject, paper, class, term, and year.
2. Calculates weighted paper scores.
3. Upserts paper-level `StudentSubjectEnrollment` records.
4. Recalculates subject-level `TermSubjectMark` records.
5. Recalculates `TermRecord.average`.
6. Updates cached `Student.performance`.
7. Recomputes class ranking.

Report cards are computed live from confirmed uploads and include:

- Subject marks and letter grades.
- Mean score and mean grade.
- Mean grade points and result band.
- Previous-term trend.
- Class ranking.
- Stream comparison.
- Generated class-teacher, DOS, and headmaster comments.
- Manual comment overrides from `TermRecord`.

Grading boundaries are currently:

- A: 80 and above
- B: 70–79.9
- C: 60–69.9
- D: 50–59.9
- F: below 50

The grade-point map also recognizes E as 1 point even though score-to-letter grading does not currently produce E. Do not alter grading semantics without confirming the school's intended policy and updating backend tests plus frontend assumptions.

### Finance

Fee structures are keyed by level group, term, and year. Tuition is common to streams within a level group. Optional extras are attached to a fee structure, and students may opt into them through `StudentFeeAssignment`.

Student fee status is computed from:

```text
tuition + opted extras - payments
```

School-fee income is always computed from `FeePayment`. It must not be stored as an `IncomeRecord`; both serializer and model validation enforce this rule.

Finance also covers non-fee income, categorized expenditure, school requirements, student fulfillment, and previous-term outstanding balances.

UGX values are stored as positive integers, which assumes whole-shilling accounting.

### Timetable

A timetable configuration contains days, rooms, ordered periods, and slots. Slots may represent lessons or breaks.

Serializer validation calls `find_conflicts()` to detect a teacher, room, or class used more than once in the same configuration/day/period. There is no automatic timetable generator. Conflict checking is currently application-level and is vulnerable to concurrent-create races.

### Notifications

Notifications may target:

- DOS scope.
- All teachers.
- One specific user.

The queryset returns only notifications relevant to the authenticated user. Mark-one-read and mark-all-read actions are available. Generic mutation permissions are currently too broad and are listed below as a priority risk.

## API Route Groups

- `/api/auth/` — login, refresh, current user
- `/api/core/` — school info, academic period, activities
- `/api/staff/` — teachers, non-teaching staff, recruitment, biometric logs
- `/api/academics/` — subjects, papers, departments, classes, assignments, report configuration, result windows
- `/api/students/` — students, parents, subjects, term enrollment, records, attendance, report cards
- `/api/results/` — result uploads and workflow actions
- `/api/finance/` — fees, payments, income, expenditure, requirements, computed summaries
- `/api/timetable/` — configurations, periods, slots
- `/api/notifications/` — notifications and read actions

DRF viewset collection responses are paginated. Pagination, endpoint paths, methods, request/response fields, enums, authentication, permissions, filtering, ordering, and error shapes are shared contracts; coordinate changes with the frontend rather than changing them silently.

## Frontend Integration Boundary

The frontend is a separate client of this REST API. Its implementation details are intentionally documented only in its own `AGENT.md`.

Backend agents need to know only that changes to API contracts, authentication, authorization, workflow states, validation/error responses, or computed values may require coordinated frontend work. In those cases, follow the cross-stack documentation rule above and do not hand off a knowingly incompatible backend.

## Seed Data

The command `python manage.py seed_demo_data` loads the exported frontend demonstration dataset from:

`apps/core/management/commands/_seed_data/mockdata_export.json`

It creates users, staff, academics, students, historical enrollment, results, finance, requirements, recruitment, attendance, and dashboard activities.

For current-period results, the seed command replays confirmed uploads through `apply_result_upload()` instead of separately seeding calculated marks. Historical terms without source uploads are seeded directly.

`python manage.py seed_demo_data --reset` deletes application data in reverse dependency order before reseeding. Treat `--reset` as destructive and never run it against an unknown or production database without explicit authorization and a verified backup.

Demo account credentials and the fallback seed password are development-only and must not be used in production.

## Known Risks and Priority Improvements

### High priority: authorization and privacy

Several APIs permit any authenticated user to read sensitive school-wide data, including student and parent information, result uploads, report cards, staff records, fee status, and finance summaries. Define and enforce intended read scopes for teachers, specialized staff, administrators, and headmasters.

`NotificationViewSet` currently allows any authenticated user to use generic create/update/delete operations. Restrict creation and broadcast capability to authorized roles, restrict read-status updates to safe actions, and disable unnecessary generic methods.

### High priority: result submission integrity

Initial result creation does not fully enforce that:

- The teacher is assigned to the selected class and subject.
- The paper belongs to the subject.
- Submitted students belong to the class and applicable subject enrollment.
- Student IDs are unique within the request.
- Term, result type, and year use valid domain values.
- Weight is within an approved range.
- The result submission window is currently open.

Add serializer/service validation and integration tests before treating result submission as production-safe.

### High priority: transactional consistency and concurrency

Result confirmation marks an upload confirmed before `apply_result_upload()` opens its transaction. A failure can leave a confirmed upload with partially absent derived state. Enclose the transition and all derived updates in one transaction and consider row locks/idempotency.

Review and rejection actions use read-check-write sequences without locking. Hiring the same candidate concurrently can create duplicate accounts. Timetable conflict checks can race. Use transactional services, `select_for_update()` where appropriate, and state-transition guards.

### Validation and error handling

Some views directly convert query parameters with `int()` or perform model `.get()` calls without consistently translating malformed input and missing rows into clean API errors. Use request serializers, `get_object_or_404()`, and consistent validation.

Validate cross-model relationships, not only foreign-key existence. Database constraints should back critical invariants whenever MySQL semantics permit it.

The uniqueness constraint for paperless `StudentSubjectEnrollment` rows does not prevent duplicates on MySQL because NULL values are treated as distinct in unique indexes. Preserve the application-level upsert protection or implement a stronger schema strategy.

### Performance

Fee status, requirement status, report-card ranking, stream comparison, and result application include per-student or per-record queries. Profile realistic school-size datasets and replace N+1 patterns with aggregation, batching, or carefully selected caching where justified.

### Finance data quality

`ExpenditureRecord.period` is free text, and summary code infers the term/year from the text or transaction date. Prefer explicit normalized term and year fields for reliable reporting.

There is no visible immutable ledger, reversal workflow, reconciliation, approval chain, or comprehensive audit trail for financial mutations. These should be considered before production financial use.

### Production operations

Current defaults are development-oriented:

- `DEBUG` defaults to true.
- A fallback insecure Django secret is present.
- Example database credentials are weak.
- Docker runs Django's development server.
- No Celery worker service is defined.
- Celery executes eagerly by default.
- No visible rate limiting or login throttling exists.
- No production media strategy, backup policy, structured logging, monitoring, or deployment health checks are defined for the application.

Production deployment should introduce secure secret management, HTTPS/security settings, a production WSGI/ASGI server, least-privilege infrastructure, backups, observability, and tested restoration procedures.

### Testing

At the time this guide was created, only the results pure-function service tests were substantive. Eighteen grading/comment tests passed. Most app-level `tests.py` files contain placeholders.

Add database-backed tests for:

- Login, refresh, and permission matrices.
- Object-level access and privacy.
- Result upload validation and every state transition.
- Atomic confirmation and result-derived records.
- Report-card ranking, historical class resolution, and configuration.
- Fee calculations and financial period behavior.
- Recruitment idempotency and password reset authorization.
- Timetable conflicts, including concurrency where feasible.
- Notification visibility and mutation permissions.
- API request/response contract behavior.

### Source control

During the initial orientation, all backend project files appeared untracked in Git. Before material development, verify repository initialization, ignore rules, commit history, and the intended branch. Never assume untracked files are disposable.

## Development Guidelines

### Preserve canonical data sources

- User is canonical for staff names and emails.
- TeacherAssignment is canonical for who teaches which class/subject/papers.
- SchoolClass is canonical for a student's current level.
- TermEnrollment is canonical for historical class enrollment.
- Confirmed ResultUpload and ResultEntry records are canonical inputs for calculated results.
- FeePayment is canonical for school-fee income.

Avoid adding denormalized copies unless there is a measured need and a documented synchronization strategy.

### Protect workflows

Use explicit services/actions for state transitions such as hiring, result approval, rejection, resending, and confirmation. Do not expose side-effectful transitions as unrestricted generic field updates.

Make workflows atomic and idempotent where requests might be retried.

### API compatibility

- Follow the cross-stack rule before changing URLs, enum values, pagination, or response shapes.
- Add a migration for every persistent model change.
- Update OpenAPI annotations/schema behavior when endpoints change.
- Return predictable validation errors that API clients can safely display.
- Keep enum spelling and capitalization aligned across the shared contract.

### Security

- Apply least-privilege permissions to reads and writes.
- Never trust client-supplied IDs without scope validation.
- Do not log passwords, access tokens, refresh tokens, or sensitive personal/financial data.
- Generated passwords are returned once; treat them as secrets.
- Avoid exposing `.env`, database dumps, or student records in tool output or commits.

### Data and migrations

- Check migration drift with `python manage.py makemigrations --check --dry-run`.
- Review generated migrations before applying them.
- Consider MySQL-specific constraint and NULL behavior.
- Do not run destructive seed resets or broad deletes without explicit authorization.

### Testing and verification

Proportional minimum checks for backend changes:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Use the repository virtual environment executable when necessary:

```bash
.venv/bin/python manage.py check
```

For cross-stack changes, use the frontend guide to determine its required checks; do not duplicate those commands or assumptions here.

Some backend checks require a working MySQL/Redis environment. If infrastructure is unavailable, report exactly which checks ran and which could not run; do not claim full verification.

### Documentation governance and approval lifecycle

The agent guides are maintained architecture documents and must evolve with the product.

For every requested change:

1. **Before planning:** read this backend guide. If frontend behavior or contracts could be affected, also read the frontend `AGENTS.md` and full `AGENT.md` before proposing an implementation.
2. **Before implementation:** identify which documented models, serializers, views, services, routes, permissions, workflows, dependencies, risks, or operational assumptions will change.
3. **During implementation:** keep the code, tests, migrations, OpenAPI behavior, shared client contract, and guides consistent. Do not document a proposed behavior as current until it is implemented and approved.
4. **After user/reviewer approval:** update the applicable guide sections to record the approved current state, new feature responsibility, new cross-app connections, API behavior, risks, and verification results.
5. **Before commit, push, or handoff:** inspect the documentation diff together with the code diff. A durable architectural or behavioral change is incomplete if the appropriate agent guide remains stale.

Update the **backend `AGENT.md`** when an approved change affects backend architecture, domain ownership, models, serializers, validation, views, services, routes, permissions, workflow states, data sources, migrations, runtime configuration, operations, security, risks, or backend testing expectations.

Update the **frontend `AGENT.md`** when an approved backend change also changes frontend behavior or its understanding of the shared contract. The frontend guide defines its own detailed documentation scope.

Update **both guides** when a change affects a shared contract or end-to-end workflow. Examples include adding or renaming an endpoint/field/enum, changing permissions, introducing a new workflow state, changing grading/finance calculations shown in the UI, changing pagination/filtering, or adding a feature that requires both backend persistence and frontend interaction.

Documentation-only wording corrections do not require artificial changes to both repositories. Temporary debugging details, unapproved proposals, and task-by-task diaries do not belong in these guides. Keep descriptions factual, durable, and representative of the code that users have approved.

## Current Verified Baseline

At the time of the initial read-only review:

- `python manage.py check` passed with no issues.
- `python manage.py makemigrations --check --dry-run` reported no model changes, though database migration-history verification could not connect to MySQL.
- All 18 tests in `apps.results.tests.test_services` passed.
- Docker runtime status could not be inspected because the shell lacked access to the Docker socket.
- No database-backed or full end-to-end verification was completed.

Re-run these checks after changes; this section is historical context, not a substitute for current validation.

## Pre-Change Checklist

Before implementing any update, confirm:

- The requested scope and affected roles are understood.
- The working tree has been inspected and unrelated changes will be preserved.
- Relevant backend domain files and migrations have been read.
- For any possible frontend impact, the frontend `AGENTS.md`, full `AGENT.md`, and relevant consumers have been read.
- Authorization and privacy effects have been considered.
- Cross-model validation and transaction boundaries have been considered.
- API compatibility implications are known.
- Tests to prove the change have been identified.
- Destructive operations, if any, have explicit authorization.

## Completion Checklist

Before handing off a change:

- Implementation and migrations are complete.
- Permissions are enforced by the backend.
- Invalid and unauthorized cases have tests.
- Relevant backend tests and system checks pass.
- Required client-side checks from the frontend guide pass when the shared contract changed.
- No secrets or unrelated files were introduced.
- Known verification limitations are stated clearly.
- The user/reviewer-approved behavior is reflected in backend `AGENT.md` where backend architecture or behavior changed.
- Frontend `AGENT.md` is updated when the shared change affects frontend behavior.
- Both guides are updated where a shared contract or end-to-end workflow changed.
- No commit, push, or completion claim leaves a known backend/frontend incompatibility undocumented or unresolved.
