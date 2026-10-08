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

The current project does not yet provide a student/parent self-service portal, payroll, library management, boarding/dormitory management, inventory procurement, automatic timetable generation, online payment-provider integration, a general double-entry accounting ledger or reversal workflow, or production-ready messaging delivery. Do not assume these exist; treat them as new features requiring explicit product and cross-stack design.

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

Redis is the default cache and Celery broker/result backend. Namecheap shared hosting explicitly selects the shared SQL cache instead. Celery remains eager by default; the VPS production Compose file provides an optional worker profile. Result processing stays synchronous.

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

- Environment profile: `DJANGO_ENVIRONMENT` is `development`, `test`, or `production`; it defaults to `development` so the existing local workflow remains available.
- Custom user model: `accounts.User`.
- Default API authentication: JWT.
- Default permission: authenticated users only.
- Default pagination: page-number pagination, 50 records per page.
- Filtering: DjangoFilterBackend, search, and ordering.
- API schema: `/api/schema/`.
- Swagger UI: `/api/docs/`.
- Time zone: `Africa/Kampala`.
- Database: MySQL/MariaDB through Django’s MySQL backend; there is no SQLite fallback. Every connection adds `STRICT_TRANS_TABLES` to its session SQL mode while preserving existing modes. This prevents silent truncation on shared hosts with non-strict defaults without changing global server settings.
- Default frontend CORS origin: `http://localhost:8080`.
- Redis logical database 1 is used for cache; database 0 is used for Celery.
- Login and token-refresh throttles use the shared Django cache: Redis by default, or the explicitly selected database cache on cPanel. Their rates and trusted-proxy count are configured through the authentication variables in `.env.example`.
- Production enables SSL redirect, secure session/CSRF cookies, content-type protection, same-origin referrer/opener policy, frame denial, and configured HSTS. Media is served by Django only while `DEBUG` is enabled.

Local environment values are documented in `.env.example`; the deliberately non-deployable production checklist is `production.env.example`. Never expose or commit real environment values.

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

Login requests are limited independently by trusted source IP and by a SHA-256 digest of the submitted username. Refresh requests have a separate source-IP limit. Throttled requests return HTTP 429 with DRF's `detail` and `Retry-After` guidance; successful authentication payloads are unchanged.

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

- `LoginView` handles credential authentication at `POST /api/auth/login/` and applies both source-IP and submitted-username throttles.
- `RefreshView` preserves SimpleJWT refresh behavior at `POST /api/auth/refresh/` and applies its own source-IP throttle.
- `MeView` returns the authenticated user at `GET /api/auth/me/`.

**Throttles (`throttles.py`):**

- `LoginIPThrottle` limits aggregate login traffic from one trusted client address.
- `LoginUsernameThrottle` limits requests against one submitted username across source addresses and stores only a digest in its cache key.
- `TokenRefreshIPThrottle` gives refresh traffic an independent limit.

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

- `Subject` stores code, unique name, O-/A-Level applicability/type, category, status, cached enrollment count, and description. The repeatable NCDC catalogue loader and school-editable categories are documented below.
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

- `reassign_class_teacher()` locks the teacher and every affected class, clears any previous class-teacher responsibility, and assigns the target class inside one transaction.
- `assign_teacher_to_class_subject()` creates/updates the class-subject and merges paper responsibility idempotently.
- `remove_teacher_from_class_subject()` removes a teacher's complete assignment for that subject/class.
- Role helpers derive subject-teacher, class-teacher, and department-head responsibilities rather than storing duplicate labels.

**Cross-app connections:** Teacher references come from staff. Students belong to SchoolClass and enroll in Subjects/Papers. ResultUpload scopes are built from class, subject, and paper. Finance uses `level_group` for fees/requirements. Timetable slots use classes, subjects, and teachers.

**Change cautions:** Validate that paper labels belong to the chosen subject and teacher allocation. Deleting protected curriculum records may affect students/results. ResultWindow currently is not enforced by result submission. `students_enrolled` is cached and can drift unless its update policy is centralized.

Class-teacher reassignment is exposed as `POST /api/academics/classes/{target_class_id}/reassign-class-teacher/` with `teacher_id`. HR/Admin/Headmaster/DOS use this action so removing the previous class and assigning the target succeed or roll back together. Clients must not reproduce this workflow with multiple class PATCH requests.

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
- `FeePayment` records immutable receipt details, a server-generated unique number, request identity, class snapshot, recorder, and payment metadata. `StudentFeeAccount`, `PaymentAllocation`, and `OpeningBalanceEvidence` preserve term charges, settlements, and imported history.
- `ExpenditureCategory` describes grouped recurring/one-off spending expectations.
- `ExpenditureRecord` records actual spending, payee, kind, free-text period, and status.
- `IncomeRecord` stores non-fee income and rejects `School Fees`, because fee income is derived from FeePayment.
- `SchoolRequirement` defines required physical items and applicable level groups.
- `StudentRequirementRecord` records quantities brought by a student.
- Enums define payment state/method, income source, expenditure kind/group/period, and requirement state.

**Serializers:** Resource serializers expose nested fee extras or readable student/category names where needed. Income validation duplicates the model-level protection against storing school-fee income.

**Views and routes:** All finance reads and writes require Bursar/Admin/Headmaster. Payments, opening balances, and historical evidence support creation and read-only retrieval; receipts also expose a controlled legacy-reconciliation action. Student statements and computed status endpoints expose period balances and allocation history. Other finance resources retain their existing CRUD routes.

**Services:** `ledger.py` owns transactionally serialized charges, receipt creation, allocations, retained credit, opening balances, and legacy reconciliation. `services.py` owns financial summaries and requirement classification. Previous balances include all earlier recorded terms; exact historical enrollment and fee structures establish charges.

**Cross-app connections:** Finance references Student and academic LevelGroup, uses core term values and period helpers, and exposes CRUD plus computed reporting endpoints to authorized clients.

**Change cautions:** Preserve financial role restrictions and FeePayment as the only source of fee-income totals. Preserve posted charge snapshots and allocation history. Reversals, refunds, and a general accounting approval chain are not implemented. Free-text expenditure period parsing remains fragile. Money uses integer UGX.

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

`ResultWindow` stores one unique opening/closing interval for a result category, term, and year. Teacher submissions are rejected unless the matching window is currently open; the DOS/Admin/Headmaster enter-and-confirm recovery path deliberately bypasses the window.

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
recorded term charge - payment allocations to that term
```

School-fee income is always computed from `FeePayment`. It must not be stored as an `IncomeRecord`; both serializer and model validation enforce this rule.

Finance also covers non-fee income, categorized expenditure, school requirements, student fulfillment, and previous-term outstanding balances.

UGX values are stored as positive integers, which assumes whole-shilling accounting.

### Timetable

A timetable configuration contains days, rooms, ordered periods, and slots. Slots may represent lessons or breaks.

Serializer validation calls `find_conflicts()` to detect a teacher, room, or class used more than once in the same configuration/day/period. Writes serialize on the parent configuration row and repeat the check under that lock. Validation also enforces configured day/period/room membership, lesson-versus-break shape, and class-subject-teacher-paper allocation. There is no automatic timetable generator.

### Notifications

Notifications may target:

- DOS scope.
- All teachers.
- One specific user.

The queryset returns only notifications relevant to the authenticated user. Generic update/delete methods are disabled. Creation validates scope/recipient consistency: only DOS/leadership may broadcast to all teachers, teachers may notify DOS or another teacher for result workflows, and unrelated roles cannot create messages. Read state is stored per user through `NotificationReadReceipt`, so reading a broadcast does not change another user's state.

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

`python manage.py seed_demo_data --reset` deletes application data in reverse dependency order before reseeding. Treat `--reset` as destructive and never run it against an unknown database without explicit authorization and a verified backup. Phase 28 blocks every `seed_demo_data` invocation when `DJANGO_ENVIRONMENT=production`, before fixture or database access.

Demo account credentials and the fallback seed password are development-only and must not be used in production.

## Known Risks and Priority Improvements

### Authorization and privacy baseline

Phase 2 narrows sensitive reads by role and object scope. Finance endpoints require Bursar/Admin/Headmaster. Bursars receive a minimal student identity DTO without family or academic fields. Teachers see only their own full staff profile, may use the minimal teacher directory for workflow addressing, and see students/results/report cards only for classes they teach or lead. Parent data remains limited to DOS and school leadership. Non-teaching staff see only their own profile; HR and school leadership retain staff-wide access. Preserve these scopes when adding endpoints and add an explicit permission test for every sensitive collection and detail route.

### Result submission integrity baseline

Result creation validates role allocation, class-subject assignment, paper ownership and teacher paper allocation, unique/known student IDs, enrolled class scope for the selected term/year, exact term/result-type choices, year/weight bounds, and an open submission window. Resends must contain exactly the original student set. DOS/Admin/Headmaster fast entry validates the same academic relationships but intentionally bypasses the teacher submission window.

### High priority: transactional consistency and concurrency

Final result confirmation locks the upload row and encloses both the Confirmed transition and `apply_result_upload()` in one outer transaction, so derived-state failure rolls the status back. Resend, entry editing, confirmation, and both rejection transitions also lock and re-check their source state before writing.

Phase 3 serializes hiring by locking the candidate row, records the created account through `RecruitmentRecord.hired_user`, and returns HTTP 409 for already-hired or non-pending candidates. Timetable period and slot writes lock their parent configuration and repeat conflict/order checks inside the transaction, preventing concurrent requests from passing the same pre-save check.

Class-teacher reassignment also uses a dedicated transactional service. It locks the teacher plus the current and target classes before changing either assignment, so a target save failure restores the complete pre-request database state automatically.

### Validation and error handling

Some views directly convert query parameters with `int()` or perform model `.get()` calls without consistently translating malformed input and missing rows into clean API errors. Use request serializers, `get_object_or_404()`, and consistent validation.

Validate cross-model relationships, not only foreign-key existence. Database constraints should back critical invariants whenever MySQL semantics permit it.

The uniqueness constraint for paperless `StudentSubjectEnrollment` rows does not prevent duplicates on MySQL because NULL values are treated as distinct in unique indexes. Preserve the application-level upsert protection or implement a stronger schema strategy.

### Performance

Fee status, requirement status, report-card ranking, stream comparison, and result application include per-student or per-record queries. Profile realistic school-size datasets and replace N+1 patterns with aggregation, batching, or carefully selected caching where justified.

### Finance data quality

`ExpenditureRecord.period` is free text, and summary code infers the term/year from the text or transaction date. Prefer explicit normalized term and year fields for reliable reporting.

Receipts and allocations now preserve student-fee settlement history, and held legacy receipts have an explicit reconciliation action. Reversals, refunds, charge adjustments, a general approval chain, and comprehensive auditing of other finance resources remain outside the implemented workflow.

### Production operations

Phase 28 separates local defaults from production startup. Production rejects debug mode, placeholder/short secrets, weak/default database credentials, unsafe/missing hosts or frontend origins, incomplete proxy/HSTS configuration, invalid Redis numbers, and malformed authentication throttle rates. Remaining operational limitations are:

- The development Docker Compose file runs Django's development server. A separate production Gunicorn image and standalone Compose file are available; see `PRODUCTION.md` for their host-proxy topology and remaining deployment requirements.
- The VPS production Compose file includes an optional Celery worker profile; shared hosting uses eager execution and no worker.
- Celery executes eagerly by default.
- Login and refresh endpoints have shared-cache application throttling (Redis or the cPanel database cache), but there is no gateway/WAF-level rate limit, distributed abuse monitoring, or account-compromise alerting. DRF's cache throttle is defense-in-depth and is not an absolute concurrency or denial-of-service control.
- Private media persistence, minimal liveness/readiness checks, and local container log rotation are implemented. Backup scheduling/restoration, off-host log collection, external monitoring/alerts, and real-domain verification still require hosting configuration.

Production deployment should introduce secure secret management, HTTPS/security settings, a production WSGI/ASGI server, edge rate limiting, least-privilege infrastructure, backups, observability, and tested restoration procedures.

## Production Deployment Configuration

Phase 28 makes production configuration fail safe. `DJANGO_ENVIRONMENT=production` enables the HTTPS policy and validates every access-critical value while Django settings load. An invalid deployment exits with `ImproperlyConfigured: Unsafe production configuration` and lists variable names/reasons without printing secrets. Development remains the default when `DJANGO_ENVIRONMENT` is absent.

`production.env.example` is the copyable variable checklist. Its public domains reflect the approved school addresses, but its placeholder secrets and infrastructure values are intentionally non-deployable; replace them rather than deploying the file unchanged. Store real values in the deployment platform's encrypted secret/config service, not Git, an image layer, logs, chat, or this guide.

### Required production values

The following is a format example, not the school's final secret or domain selection:

```dotenv
DJANGO_ENVIRONMENT=production
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=<unique-generated-secret-at-least-50-characters>

DJANGO_ALLOWED_HOSTS=api.<real-school-domain>
CORS_ALLOWED_ORIGINS=https://portal.<real-school-domain>
CSRF_TRUSTED_ORIGINS=https://portal.<real-school-domain>

DB_NAME=hopeful_future_sms
DB_USER=hopeful_future_app
DB_PASSWORD=<unique-generated-database-password-at-least-20-characters>
DB_HOST=<private-database-hostname>
DB_PORT=3306

REDIS_HOST=<private-redis-hostname>
REDIS_PORT=6379
REDIS_CACHE_DB=1
REDIS_CELERY_DB=0

DJANGO_TRUST_PROXY_SSL_HEADER=True
DRF_NUM_PROXIES=1

DJANGO_SECURE_HSTS_SECONDS=3600
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
DJANGO_SECURE_HSTS_PRELOAD=False

AUTH_LOGIN_IP_THROTTLE_RATE=30/minute
AUTH_LOGIN_USERNAME_THROTTLE_RATE=5/minute
AUTH_REFRESH_IP_THROTTLE_RATE=60/minute

CELERY_TASK_ALWAYS_EAGER=True
```

The matching frontend production build value is:

```dotenv
VITE_API_BASE_URL=https://api.<real-school-domain>/api
```

Do not add a trailing slash to `VITE_API_BASE_URL`. The frontend appends paths beginning with `/`. The public frontend origin must exactly match the scheme, hostname, and optional port in both backend origin lists; origin values have no path or trailing slash.

| Value | How to choose it | Incorrect-value effect |
| --- | --- | --- |
| `DJANGO_SECRET_KEY` | Generate once with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`; store it as a secret and keep it stable across application instances/restarts. | Missing, placeholder, `django-insecure-*`, low-variety, or shorter than 50 characters stops startup. Changing it invalidates signed Django sessions and other signed values. |
| `DB_NAME` | Dedicated production database, recommended `hopeful_future_sms`. | Wrong name causes database connection or migration failure. |
| `DB_USER` | Dedicated least-privilege application account, recommended `hopeful_future_app`; never `root`. Grant only the privileges required for runtime and controlled migrations. | `root`, missing, or incorrect user stops validation or database login. |
| `DB_PASSWORD` | Generate independently, for example `openssl rand -hex 32`; minimum enforced length is 20 characters. | Default, placeholder, short, or incorrect password stops validation or database login. |
| `DB_HOST` / `DB_PORT` | Private DNS/service address reachable from the backend; MySQL normally uses `3306`. Do not use a public database endpoint without provider-required TLS and network controls. | Wrong routing prevents startup/runtime database access. |
| `DJANGO_ALLOWED_HOSTS` | Public backend hostname only, such as `api.school-domain.ug`; comma-separate additional intentional hostnames. Do not include `https://`, a port, path, wildcard, localhost, or reserved example name. | A missing host stops startup; a real request using an unlisted Host receives HTTP 400 `DisallowedHost`. |
| `CORS_ALLOWED_ORIGINS` | Exact public frontend origin, such as `https://portal.school-domain.ug`; comma-separate real additional frontends. | The browser blocks frontend API access even when the backend itself is healthy. |
| `CSRF_TRUSTED_ORIGINS` | Include every CORS origin using the same exact HTTPS value. Add another origin only if it is trusted to make CSRF-protected requests. | Django Admin or future cookie-based protected writes can return CSRF 403. |
| `REDIS_HOST` / `REDIS_PORT` | Private Redis service address; normal port `6379`. Restrict it at the network layer. | Cache-backed login throttling and other cache operations fail when Redis is unreachable. |
| `REDIS_CACHE_DB` / `REDIS_CELERY_DB` | Keep separate non-negative logical DBs; current contract is cache `1`, Celery `0`. | Sharing them makes cache flushes capable of destroying Celery state. |
| Authentication throttle rates | Keep the Phase 27 defaults unless measured school traffic justifies change. Accepted forms include `5/minute` and `100/hour`. | Invalid syntax stops production startup; overly low rates temporarily block legitimate shared-network users. |

The production profile automatically sets `SECURE_SSL_REDIRECT=True`, `SESSION_COOKIE_SECURE=True`, `CSRF_COOKIE_SECURE=True`, `SESSION_COOKIE_HTTPONLY=True`, `SESSION_COOKIE_SAMESITE='Lax'`, `CSRF_COOKIE_SAMESITE='Lax'`, `SECURE_CONTENT_TYPE_NOSNIFF=True`, `SECURE_REFERRER_POLICY='same-origin'`, `SECURE_CROSS_ORIGIN_OPENER_POLICY='same-origin'`, and `X_FRAME_OPTIONS='DENY'`. Do not weaken them to work around a proxy or domain problem; correct the deployment topology instead.

### HTTPS, proxy, and client-IP values

`DJANGO_TRUST_PROXY_SSL_HEADER=True` is safe only when the final trusted proxy removes any client-supplied `X-Forwarded-Proto` header and writes its own value. Otherwise a caller may spoof whether Django considers a request secure. `DRF_NUM_PROXIES` controls which address DRF trusts for Phase 27 throttling and must match the sanitized proxy chain.

| Request path to Django | `DJANGO_TRUST_PROXY_SSL_HEADER` | `DRF_NUM_PROXIES` | Requirement |
| --- | --- | --- | --- |
| Django receives HTTPS directly | `False` | `0` | No forwarded security headers are trusted. |
| Client -> one trusted TLS-terminating Nginx/ingress -> Django | `True` | `1` | The proxy strips incoming forwarded headers and writes canonical values. |
| Client -> two trusted proxy hops -> Django | `True` | `2` | Both hops and the exact `X-Forwarded-For` behavior are verified by the operator. |

If the SSL-header trust value is wrong, production can enter an HTTPS redirect loop. If the proxy count is too low, many users may share one throttle identity; if too high, callers may influence the selected address and evade limits. Confirm these two values with the actual hosting/network provider before opening traffic.

Start HSTS at `3600` seconds only after HTTPS works end-to-end, including the API hostname. After sustained validation, increase it to `31536000`. Keep `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False` and `DJANGO_SECURE_HSTS_PRELOAD=False` until every subdomain is permanently HTTPS-capable and the school explicitly accepts the difficult rollback consequences. Enabling preload in settings alone does not submit the domain to browser preload lists.

### Deployment preflight and access verification

Before public traffic:

1. Provision final backend/frontend DNS names and valid TLS certificates.
2. Create the least-privilege database user/database and the selected shared cache: private Redis for the VPS, or the database cache table for cPanel as described in `CPANEL.md`; verify access from the backend runtime.
3. Put the required values in the platform secret/config store and confirm the frontend production build used the matching `VITE_API_BASE_URL`.
4. Run these commands inside the exact configured backend image/runtime:

```bash
python manage.py check
python manage.py check --deploy --tag security
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

5. Take and verify a restorable database backup before applying migrations, then run `python manage.py migrate` once through the controlled release process.
6. Start the backend and verify HTTPS has no redirect loop, the API hostname is accepted, and HTTP redirects to HTTPS.
7. From the real frontend origin, verify CORS preflight/login, token refresh, logout, and one permitted read for every role. Verify an unauthorized role remains denied.
8. Verify login throttling against the selected shared cache and review logs without recording credentials or tokens.
9. Increase HSTS only after monitoring confirms HTTPS stability. Never run `seed_demo_data` in production; Phase 28 blocks it even if invoked accidentally.

With the safe first-rollout HSTS values (`3600`, subdomains `False`, preload `False`), the tagged deployment check must exit successfully and report only Django advisories `security.W005` and `security.W021`. Those advisories accurately record that subdomains/preload are being deferred; do not silence them. Any other security warning must be resolved before traffic opens. After every subdomain is permanently HTTPS-ready and the school approves preload, change HSTS to `31536000`/`True`/`True` and require the mature strict gate:

```bash
python manage.py check --deploy --tag security --fail-level WARNING
```

An unfiltered `python manage.py check --deploy` also runs drf-spectacular schema diagnostics; its existing OpenAPI warnings are tracked separately and are not Django security-setting failures. Do not silence them or use them as a reason to skip the tagged security gate.

### Troubleshooting without weakening security

| Symptom | Check first |
| --- | --- |
| Startup says `Unsafe production configuration` | Read every listed variable name/reason, correct the secret store, and restart. Never paste real values into logs or tickets. |
| HTTP 400 / `DisallowedHost` | The request's public backend hostname must appear exactly in `DJANGO_ALLOWED_HOSTS` without scheme or port. |
| Browser reports a CORS error | Match the frontend's visible HTTPS origin exactly in `CORS_ALLOWED_ORIGINS`; confirm the frontend is calling the correct API URL. |
| Django Admin/future cookie write returns CSRF 403 | Match the frontend/admin HTTPS origin in `CSRF_TRUSTED_ORIGINS` and confirm proxy HTTPS detection. |
| Repeated HTTPS redirects | Confirm the TLS-terminating proxy sanitizes and sets `X-Forwarded-Proto=https`, then verify `DJANGO_TRUST_PROXY_SSL_HEADER`. Do not disable SSL redirect. |
| Legitimate users receive HTTP 429 together | Verify `DRF_NUM_PROXIES` against the real proxy chain before raising limits. |
| Login fails with a cache/Redis error | Verify private Redis DNS, port, service health, network policy, and logical DB values. |
| Database connection fails | Verify application-user credentials, private hostname/port, grants, provider TLS requirements, and migration state. |

Correct configuration and restart is the rollback for Phase 28 settings failures; it does not require reverting code or database data. The VPS WSGI/runtime procedure is in `PRODUCTION.md`; the initial Namecheap shared-hosting procedure is in `CPANEL.md`. External backup, monitoring, and deployment acceptance gates remain mandatory.

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

The backend now has an audited local Git baseline on `main`, beginning with commit `b692448` (`Initial school management backend`). The real `.env`, virtual environments, bytecode, logs, media, and local runtime artifacts are ignored. No remote is configured yet; do not attach or push to the separate `hopeful-future-website_backend` repository, which belongs to another project for the same school. Configure a remote only when the dedicated SMS-backend repository is known and explicitly approved.

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
- Docker Compose successfully built and started the declared web, MySQL, and Redis services; MySQL and Redis reported healthy.
- All committed migrations were applied, and `python manage.py makemigrations --check --dry-run` reported no model changes.
- All 18 tests in `apps.results.tests.test_services` passed.
- The full discovered backend suite also contained only those same 18 pure service tests; database-backed API/workflow coverage remains absent.
- OpenAPI generation completed with seven unique schema problems affecting APIViews, notification schema inspection, serializer method types, and enum naming.
- The audited local Git baseline is commit `b692448`; no remote is configured.

Re-run these checks after changes; this section is historical context, not a substitute for current validation.

## Phase 25: Atomic Result-Workflow Notifications

- `ResultUploadViewSet` owns notifications required by governed upload transitions. Submission, resend, Class Teacher confirmation/rejection, and DOS confirmation/rejection create notification records inside the same `transaction.atomic()` boundary as their result state change.
- Submission targets the assigned Class Teacher, or the DOS broadcast when no Class Teacher exists. Resend targets the Class Teacher. Class Teacher confirmation targets DOS and the distinct submitting teacher; rejection targets the distinct submitting teacher. DOS confirmation targets the submitting teacher and distinct Class Teacher; DOS rejection targets the Class Teacher.
- Notification recipients and teacher display names are derived from backend relationships (`Teacher.user`, `SchoolClass.class_teacher`, and `ResultUpload.teacher`). Never accept workflow recipient identity or display names from the client.
- If result application or any other operation in the transition transaction fails, its notification rolls back with the status change. Frontends must not compensate with a separate notification request after these endpoints succeed.
- Result-window announcements remain separate notification creation requests because window scheduling is not a `ResultUpload` state transition.
- Verification baseline after this change: `python manage.py check` passes, migration drift reports no changes, focused result-security tests pass 10/10, and the complete backend suite passes 54/54 using the Docker MySQL environment.

## Phase 26: Deterministic Academic Pagination

- `SubjectViewSet` orders by `name`, then `id`; `ResultWindowViewSet` orders by descending `year`, then `term`, `result_type`, and `id`; `ReportCardConfigViewSet` orders by descending `year`, then `term` and `id`.
- These queryset-level orderings make DRF pagination deterministic without changing model metadata or creating a migration. Preserve a unique final `id` tie-breaker whenever these sort keys change.
- Endpoint paths, filters, serializers, pagination envelopes, and role permissions are unchanged. Clients may rely on stable traversal across all pages but must still use backend IDs as identity.
- The teacher academic-reference test promotes `UnorderedObjectListWarning` to an exception, guarding these paginated endpoints against future unordered querysets.
- Verification baseline: focused academics tests pass 9/9, the complete backend suite passes 54/54 without unordered-pagination warnings, `manage.py check` passes, and migration drift reports no changes.

## Phase 27: Authentication Abuse Protection

- `POST /api/auth/login/` uses two cache-backed limits: 30 requests per minute from one trusted source IP and 5 requests per minute against one submitted username by default. `POST /api/auth/refresh/` has an independent default of 60 requests per minute per trusted source IP.
- Operators may change the limits with `AUTH_LOGIN_IP_THROTTLE_RATE`, `AUTH_LOGIN_USERNAME_THROTTLE_RATE`, and `AUTH_REFRESH_IP_THROTTLE_RATE`. Use DRF rate strings such as `5/minute` or `100/hour`; invalid values are deployment configuration errors.
- `DRF_NUM_PROXIES` defaults to `0`, so client-supplied `X-Forwarded-For` values are not trusted in direct deployments. Set it only to the exact number of trusted reverse proxies that sanitize that header; a wrong value can either combine unrelated users or let callers evade the IP limit.
- Username throttle keys contain a secret-keyed SHA-256 digest rather than the submitted username. Malformed non-object requests skip only the username-specific limiter and remain covered by the source-IP limiter before serializer validation.
- Normal successful login and refresh payloads are unchanged. Limited requests return HTTP 429 with a `detail` explanation and `Retry-After`; the portal displays that explanation and does not create authentication storage.
- These application limits depend on the shared Redis cache and are defense-in-depth. They do not replace reverse-proxy/WAF limits, monitoring, alerting, or stronger credential-security controls, and DRF cache throttles may be approximate under highly concurrent traffic.
- Phase 27 adds no model or schema migration. Verification passes 5/5 focused account tests and 59/59 complete backend tests; Django system checks and migration-drift checks are clean. Frontend type checking, lint, 44/44 unit tests, production build, and a strict no-retry run of all 41 browser scenarios pass.

## Phase 28: Production Security Configuration

- `DJANGO_ENVIRONMENT` now selects `development`, `test`, or `production` and defaults to `development`. Existing localhost hosts/origins, HTTP operation, Docker `runserver`, eager Celery behavior, and developer commands remain available without production HTTPS enforcement.
- Production settings fail while importing if required variables are missing or if debug mode, placeholder/weak secrets, root/weak database credentials, wildcard/local/example hosts, non-HTTPS frontend origins, incomplete proxy/HSTS values, invalid Redis numbers, or malformed authentication throttle rates are supplied. Error output names the settings to correct without printing their secret contents.
- The production profile automatically enables SSL redirect, secure session/CSRF cookies, HTTP-only session cookies, `Lax` same-site cookies, content-type protection, same-origin referrer/opener policy, and frame denial. HSTS requires at least 3600 seconds; subdomain/preload adoption remains an explicit staged decision.
- `DJANGO_TRUST_PROXY_SSL_HEADER` and `DRF_NUM_PROXIES` are independent explicit production choices. Preserve the topology rules in “Production Deployment Configuration”; weakening SSL redirect or trusting unsanitized forwarded headers is not an acceptable fix for a redirect or throttling problem.
- `production.env.example` is a non-deployable backend checklist with approved public domains and rejected placeholder secrets/infrastructure values. The frontend companion template supplies `VITE_API_BASE_URL`; both agent guides document exact domain/origin alignment, value generation, deployment preflight, HSTS rollout, access verification, and symptom-based troubleshooting.
- `seed_demo_data` raises `CommandError` immediately in production, including without `--reset`. Demo credentials and fixtures cannot be introduced through that management command once the production profile is active.
- This phase changes configuration behavior only: no model migration, stored data, route, serializer, permission, or normal API payload changed. Production serving, media, backups, monitoring, health checks, and a Celery worker remain later operational work.
- Verification baseline: 15/15 focused production configuration/transport tests and 74/74 complete backend tests pass; local `manage.py check`, Python compilation, migration-drift checks, and a simulated mature-production `check --deploy --tag security --fail-level WARNING` pass. Frontend type checking, lint, production build, 44/44 unit tests, and a strict no-retry run of all 41 browser scenarios pass.

## Phase 29: Production WSGI Runtime

- `Dockerfile.production` uses a separate dependency build stage and runs Gunicorn as non-root UID/GID 10001. `requirements-production.txt` adds pinned Gunicorn without changing local development dependencies. `.dockerignore` excludes environment files, local runtime artifacts, and Git metadata from image build contexts.
- `compose.production.yml` is standalone, not a development override. It requires `PRODUCTION_ENV_FILE`, forces production/debug-off settings, binds only host loopback port 8001, drops capabilities, and uses a read-only root filesystem with writable `/tmp`. Provision reachable private MySQL/Redis services and a same-host TLS reverse proxy separately.
- `gunicorn.conf.py` starts two synchronous workers by default, configurable with `WEB_CONCURRENCY`. Worker timeout is 60 seconds, graceful shutdown is 30 seconds, and Compose allows 45 seconds before forced termination. Startup never applies migrations or seeds data.
- Django's explicit trusted-proxy policy remains authoritative; Gunicorn's additional forwarded-header interpretation is disabled with an empty `forwarder_headers` string; its administrative control socket is disabled for the read-only runtime. Access logs omit query strings, headers, and bodies. Server logs go to stdout/stderr for platform collection.
- `PRODUCTION.md` documents the VPS build, preflight, controlled migration/startup, proxy topology, and rollback boundaries. The image collects static files, Compose mounts private persistent media, and an optional worker profile provides Celery. Health probes and bounded local logs are implemented; real infrastructure, backups, centralized logging/monitoring, and public-domain verification remain external acceptance gates.
- This phase adds server packaging only; API contracts and frontend behavior are unchanged. Existing development Compose behavior remains available.

## Shared Hosting and Operational Deployment Support

- The user will perform the initial installation through cPanel (File Manager, Setup Python App, and its available terminal/management controls); do not assume an SSH connection is configured. Follow `CPANEL.md` for the controlled release.
- The first deployment target is Namecheap shared hosting with cPanel; Linode is the later VPS target. The portal is `https://www.hopefulfuture.ac.ug/schoolsystem/`, the API base is `https://api.hopefulfuture.ac.ug/api`, and the school website remains at its existing root. Backend CORS/CSRF origin values are `https://www.hopefulfuture.ac.ug` without a path. `CPANEL.md` is the shared-host runbook, while `PRODUCTION.md` and the production Compose file require a Docker-capable VPS.
- `passenger_wsgi.py` provides the cPanel `application` entry point. `requirements-cpanel.txt` reuses the pure-Python PyMySQL dependency profile. Select Python 3.12 and verify the account's SQL compatibility before accepting data.
- `DJANGO_CACHE_BACKEND` is `redis` by default or explicitly `database`. Database mode uses Django DatabaseCache and the `sms_cache` table, created with `manage.py createcachetable`, for cross-process throttling. It requires eager Celery, omits Redis production requirements, and preserves HTTPS, secret, database, and authentication-rate validation. Do not silently fall back to local-memory caching.
- `DJANGO_STATIC_ROOT` and `DJANGO_MEDIA_ROOT` accept absolute deployment paths. Static assets may be public; media remains private. Student registration accepts private device-photo uploads, served only by the authenticated, academically scoped student photo endpoint; legacy photo URLs remain readable.
- `GET`/`HEAD /health/live/` returns uncached `{"status":"ok"}` without dependency access. `/health/ready/` verifies SQL and the selected cache and returns minimal HTTP 503 on dependency failure. Only these exact paths bypass SSL redirect for internal probes; the VPS proxy template blocks them publicly. cPanel external monitoring must use HTTPS.
- The VPS runtime uses a private media volume, collected static assets, bounded local container logs, and an optional `worker` profile. `deploy/nginx.conf.example` is an unconfigured host-proxy template with sanitized headers and edge authentication limits.
- Database-cache throttles remain approximate under concurrent requests and add SQL load. External backups, restore rehearsal, provider log collection/alerts, domain/TLS configuration, and real-host smoke tests are separate deployment acceptance requirements; local tests cannot certify those services.

### Confirmed cPanel installation details

- The school domain is an additional domain on the hosting account whose main domain is `sisit.it.com`. The backend application root is `/home/sisitzyt/hopeful-future-sms`; its public API document root is `/home/sisitzyt/api.hopefulfuture.ac.ug`. Keep backend source and secrets in the private application root.
- The existing school document root is `/home/sisitzyt/public_html/hopefulfuture.ac.ug`; portal assets belong only in its `schoolsystem/` subdirectory, not directly in `/public_html/schoolsystem/`.
- On premium65, Namecheap support confirmed that forwarded protocol reflects the actual HTTP/HTTPS connection and client spoofed protocol values are not trusted. Support also tested that the actual connection IP reaches the application without the spoofed IP. This deployment uses `DJANGO_TRUST_PROXY_SSL_HEADER=True` and `DRF_NUM_PROXIES=1`. Reverify if the proxy/CDN topology changes; do not generalize this choice to all providers.
- Python 3.12.14 and cPanel dependency installation were confirmed by the operator; production settings checks passed and security checks returned only the expected W005/W021 staged-HSTS advisories. The operator applied the strict-mode settings update and confirmed a clean MariaDB database check. All initial migrations, database-cache table creation, the A-Level catalogue load, and static collection then completed successfully. Both live health endpoints returned `ok`, and Django Admin login and styling were verified by the operator on 2026-10-07. On 2026-10-08, the operator confirmed successful portal login and page loading at `/schoolsystem/`, and confirmed the existing school website remains unchanged. These are operator-reported smoke checks; live student/finance workflows, role-specific access, backups/restore validation, and monitoring acceptance remain outstanding.
- The database-password minimum remains 20 characters. Never store real passwords or Django keys in these guides. Keep the application stopped during initial configuration and migrations.

### Strict SQL mode verification

- The connection initializer is exercised against both empty SQL mode and a non-strict mode containing `NO_ENGINE_SUBSTITUTION`, confirming strict mode is added and existing modes survive.
- On 2026-10-07, all 14 focused database-mode and environment-profile tests passed. Local database checks passed with both mysqlclient and the cPanel PyMySQL driver against MySQL. The full backend suite also passed all 107 tests. Migration drift is clean; this fix requires no schema migration.
- These local checks do not certify the provider's MariaDB connection. After replacing the hosted `config/settings.py`, require `check --database default` and `migrate --plan` to complete without `mysql.W002` before applying the initial migrations.

### Release packaging and verified baseline

- `scripts/package_cpanel.py` produces a source-only ZIP from an explicit allowlist and Python files under `apps`/`config`. It rejects symlinks or paths outside the repository and refuses to overwrite an existing archive. Real environment files, local data, logs, virtual environments, and Git metadata are excluded. Regenerate the archive after source or included-guide changes.
- The VPS image validates Gunicorn configuration during its build before collecting static assets. Synthetic test settings are used for local verification; they are never deployment credentials.
- Verified on 2026-09-29: all 85 backend tests passed with MySQL; Django system checks passed and migration drift reported no changes. Passenger imported successfully in production mode with the shared database cache.
- The production image built successfully. An isolated non-root, read-only container verified liveness HTTP 200, readiness HTTP 503 when dependencies are unavailable, API HTTP-to-HTTPS redirect HTTP 301, and graceful shutdown. This failure-path check does not establish healthy connectivity to production SQL/cache services.
- Companion frontend checks passed: TypeScript, lint, 44 unit tests, 41 application browser scenarios, and four compiled `/schoolsystem/` deployment scenarios with mocked API responses and zero retries.
- Local release preparation is complete; no live deployment or existing-school-website modification has been performed. Actual cPanel provisioning, uploads, secret configuration, database setup, DNS/TLS, backup/restore rehearsal, monitoring, and real-origin workflow checks remain required before declaring the deployment complete.

## Student Photos, Subject Catalogue, and Fee History

### Student photographs

- Student create/update accepts multipart `photo` data. `photo_url` is read-only legacy data; `has_photo` indicates a private uploaded image. Storage paths are never serialized.
- Pillow validates actual JPEG, PNG, or WebP content (maximum 5 MiB and 20 million pixels), applies EXIF orientation, removes metadata by re-encoding, and stores a UUID-named JPEG bounded to 1200×1200. Install the updated requirements in every runtime.
- `GET /api/students/{id}/photo/` streams the image with `private, no-store` and `nosniff`. Academic role/object scope applies; Bursar/HR/unrelated teachers cannot access it. Report-card and teacher student DTOs include `has_photo` where authorized.
- Keep `DJANGO_MEDIA_ROOT` writable and outside public document roots; back it up with SQL. Old/replaced file cleanup is not automated.

### A-Level catalogue and categories

- `python manage.py load_advanced_subjects` or authorized `POST /api/academics/subjects/load-advanced-catalogue/` loads the 40-subject [NCDC Higher Secondary menu](https://ncdc.go.ug/directorates/) checked on 2026-10-01. This is reference data, not demo seeding, and the command is permitted in production.
- The loader preserves existing identities, codes, papers, and manually assigned categories; known alternative names are matched. New entries use internal `NCDC-AL-*` identifiers, never claimed to be UNEB examination codes. Teaching allocations and examination paper definitions require school configuration.
- Categories are `Sciences`, `Arts`, `Languages`, `Technical`, `General`, or `Unclassified`; they are school-editable browsing aids, not official subject-combination eligibility rules. The subjects endpoint supports `category` filtering.

### Student fee accounts and automatic settlement

- A new student has zero previous balance unless actual earlier term enrollment/charges or an explicit imported opening balance exists. Never invent debt from the current class or reuse another term's fee structure.
- `StudentFeeAccount` snapshots each term's historical class, tuition/extras or imported net balance, source, notes, and recorder. Posted charges remain stable after promotion or later fee changes. Fee structures/extra assignments with posted charges cannot be rewritten through their guarded API operations.
- Every payment requires a client UUID `request_id`; an identical retry returns the original receipt, and changed details using that UUID are rejected. The server generates a unique `HFSS-*` receipt. Generic payment update/delete and Django Admin payment mutation are disabled.
- Within a transaction locked on the student, payment first settles the selected term, then applies excess to the oldest outstanding accounts. Unused funds remain credit. Later enrollment, fee-structure creation, or opening-balance creation applies available credit automatically. No duplicate cash receipt is created for a transfer.
- Every allocation retains its receipt, destination term/year/class, amount, resulting term balance, reason, and timestamp. The original payment amount/date/method/notes and recorder remain traceable. Earlier-term payments require actual outstanding debt; `arrears_only` additionally restricts the target to before the active academic period.
- `GET /api/finance/students/{id}/statement/` returns all term accounts, receipts/allocations, opening evidence, outstanding total, and retained credit. `payments/?receipt_no=...` traces a receipt across periods. Student status returns cumulative `prev_balance`, selected-term paid/balance, credit, historical class/level, and whether a term charge exists.
- `POST /api/finance/opening-balances/` imports a positive net amount for an earlier term with historical class and required provenance notes. Duplicate accounts and periods with existing receipts are rejected. `opening-balance-evidence/` appends dated historical charges/payments and references where available; evidence explains the imported net amount and never counts as new cash or reduces the balance again.
- Migration `finance.0004` preserves old receipt numbers and allocates only against exact historical enrollment/prices. Receipts without sufficient historical context are held with `requires_reconciliation`; they cannot be spent as credit. After recording original enrollment and full charges, `POST /api/finance/payments/{id}/reconcile/` releases and allocates a held receipt idempotently. An imported net opening balance cannot substitute for its original full charge.
- Fee-income reports continue summing original FeePayment amounts by their designated period, while account balances sum destination allocations. Opening evidence and internal allocations are never new income. A general reversal/refund or charge-adjustment workflow is not yet available.

### Upgrade and verification

Install updated dependencies, review/back up the database, apply migrations, then load the catalogue with `load_advanced_subjects`. Verify private media storage and the real-host photo/payment workflows before accepting production data. Regenerate cPanel packages after these source changes; archives produced before this update are stale. The verification results below supersede the earlier historical release baselines for these changes.

### Verification of student and finance updates — 2026-10-03

- Django system checks and migration-drift checks pass. The complete backend run passed 105 tests; the subsequent 18-test finance/catalogue run also passed and includes the newly added receipt-backfill test and final catalogue conflict-handling changes.
- Frontend TypeScript and ESLint checks pass; all 46 unit tests, 45 application browser scenarios, and four compiled `/schoolsystem/` deployment scenarios pass without retries. Browser API responses are mocked; backend tests exercise MySQL-backed behaviour.
- The local development database was backed up before applying the new migrations, and the NCDC catalogue loaded successfully. No production database or school website was changed. Existing production acceptance and cPanel package-regeneration requirements still apply.

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


## O-Level catalogue update — 2026-10-08

- `load_ordinary_subjects` and authorized POST `/api/academics/subjects/load-ordinary-catalogue/` merge the 35 individual O-Level subjects published at https://ncdc.go.ug/directorates/ (checked 2026-10-08). Admin, Headmaster and DOS can load the menu; other roles cannot write it.
- Codes `NCDC-OL-xx` are internal identifiers, not UNEB examination codes. Loading is atomic and repeatable; existing aliases, IDs, codes, papers, categories, inactive status and configured O-Level types are preserved. Shared A-Level subjects gain O-Level availability; History & Political Education and O-Level ICT remain separate from History and Principal/Subsidiary ICT.
- Seven subjects compulsory throughout S1–S4 default to Compulsory; other choices default to Optional. This is a subject menu, not automatic curriculum compliance: configure additional S1–S2 requirements, religious alternatives and school offerings through class subject assignments. No papers or enrollment are created by loading.
- Frontend offers separate O-Level/A-Level load buttons and retains category filters. O-Level success refreshes the list and clears filters to show O-Level choices. No schema migration or dependency change is required. Live installation of this update is still pending.
