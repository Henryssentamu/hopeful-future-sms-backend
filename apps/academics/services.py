"""
Port of src/lib/classAssignments.ts and src/lib/teacherRoles.ts. The
frontend versions operated on an in-memory array and returned a new copy;
here they're plain ORM operations against the real tables, but the
*behavior* (idempotent paper merge, remove-all-papers-for-this-teacher, role
derivation by scanning rather than a stored field) is preserved exactly.
"""

from .models import AssignmentType, ClassSubjectAssignment, Department, SchoolClass, TeacherAssignment


def assign_teacher_to_class_subject(
    school_class: SchoolClass,
    subject,
    teacher,
    papers: list[str],
    assignment_type_if_creating: str = AssignmentType.COMPULSORY,
) -> TeacherAssignment:
    """Port of assignTeacherToClassSubject(). If the class doesn't yet teach
    this subject, creates the ClassSubjectAssignment. If this teacher
    already has an assignment for it, MERGES the given papers into their
    existing set (idempotent/additive — matches the frontend's Set-union
    behavior) rather than replacing it."""
    csa, _ = ClassSubjectAssignment.objects.get_or_create(
        school_class=school_class,
        subject=subject,
        defaults={"type": assignment_type_if_creating},
    )
    ta, created = TeacherAssignment.objects.get_or_create(
        class_subject_assignment=csa,
        teacher=teacher,
        defaults={"papers": list(dict.fromkeys(papers))},
    )
    if not created:
        merged = list(dict.fromkeys([*ta.papers, *papers]))
        if merged != ta.papers:
            ta.papers = merged
            ta.save(update_fields=["papers"])
    return ta


def remove_teacher_from_class_subject(school_class: SchoolClass, subject, teacher) -> None:
    """Port of removeTeacherFromClassSubject() — removes ALL of this
    teacher's papers for this subject+class in one call (no partial
    paper-removal primitive, matching the frontend exactly)."""
    TeacherAssignment.objects.filter(
        class_subject_assignment__school_class=school_class,
        class_subject_assignment__subject=subject,
        teacher=teacher,
    ).delete()


def get_subject_teacher_assignments(subject) -> list[dict]:
    """Port of getSubjectTeacherAssignments() — every (teacher, class,
    papers) triple across all classes that teach this subject."""
    return [
        {"teacher": ta.teacher, "school_class": ta.class_subject_assignment.school_class, "papers": ta.papers}
        for ta in TeacherAssignment.objects.filter(class_subject_assignment__subject=subject).select_related(
            "teacher", "class_subject_assignment__school_class"
        )
    ]


def get_teacher_roles(teacher) -> list[dict]:
    """Port of getTeacherRoles() — derived by scanning SchoolClass.class_teacher
    and Department.head_teacher, never stored directly on Teacher."""
    roles = [
        {"type": "Class Teacher", "scope": c.name}
        for c in SchoolClass.objects.filter(class_teacher=teacher)
    ]
    roles += [
        {"type": "Head of Department", "scope": d.name}
        for d in Department.objects.filter(head_teacher=teacher)
    ]
    return roles


def get_class_teacher_of(teacher) -> SchoolClass | None:
    """Port of getClassTeacherOf() — the FIRST matching class only."""
    return SchoolClass.objects.filter(class_teacher=teacher).order_by("id").first()
