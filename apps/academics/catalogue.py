"""NCDC higher-secondary subject menu, checked 2026-10-01.

Source: https://ncdc.go.ug/directorates/ (Higher Secondary Education).
Categories are school-editable browsing aids, not UNEB combination rules.
NCDC-AL codes are internal identifiers, not examination subject codes.
Existing paper definitions are retained; no examination papers are guessed.
"""
from django.db import transaction
from django.db.models import Q

from apps.core.models import AcademicPeriod
from .models import Subject

SUBJECTS = [
    ('Agriculture', 'Sciences'),
    ('Biology', 'Sciences'),
    ('Chemistry', 'Sciences'),
    ('Mathematics', 'Sciences'),
    ('Physics', 'Sciences'),
    ('Subsidiary Mathematics', 'Sciences'),
    ('Art and Design', 'Arts'),
    ('Christian Religious Education', 'Arts'),
    ('Economics', 'Arts'),
    ('Entrepreneurship Education', 'Arts'),
    ('Geography', 'Arts'),
    ('History', 'Arts'),
    ('Islamic Religious Education', 'Arts'),
    ('Literature', 'Arts'),
    ('Music', 'Arts'),
    ('Arabic', 'Languages'),
    ('Chinese', 'Languages'),
    ('French', 'Languages'),
    ('German', 'Languages'),
    ('Kiswahili', 'Languages'),
    ('Latin', 'Languages'),
    ('Ateso', 'Languages'),
    ('Dhopadhola', 'Languages'),
    ('Leb Acoli', 'Languages'),
    ('Leblango', 'Languages'),
    ('Luganda', 'Languages'),
    ('Lugbarati', 'Languages'),
    ('Lumasaaba', 'Languages'),
    ('Lusoga', 'Languages'),
    ('Runyoro-Rutooro', 'Languages'),
    ('Runyankore-Rukiga', 'Languages'),
    ('Clothing and Textile', 'Technical'),
    ('Foods & Nutrition', 'Technical'),
    ('Metal Work', 'Technical'),
    ('Subsidiary ICT', 'Technical'),
    ('Technical Drawing', 'Technical'),
    ('Wood Work', 'Technical'),
    ('Principal ICT', 'Technical'),
    ('General Paper', 'General'),
    ('Physical Education', 'General'),
]
ALIASES = {
    "Christian Religious Education": ["CRE", "Christian Religious Education (CRE)"],
    "Islamic Religious Education": ["IRE", "Islamic Religious Education (IRE)"],
    "Mathematics": ["Principal Mathematics"],
    "Literature": ["Literature in English"],
    "Art and Design": ["Art & Design", "Fine Art"],
    "Entrepreneurship Education": ["Entrepreneurship"],
    "Foods & Nutrition": ["Foods and Nutrition"],
}


@transaction.atomic
def load_advanced_subjects():
    # Serialize repeated catalogue loads without changing existing identities.
    period = AcademicPeriod.load()
    AcademicPeriod.objects.select_for_update().get(pk=period.pk)
    alias = "default"
    for index, (name, category) in enumerate(SUBJECTS, 1):
        candidates = [name, *ALIASES.get(name, [])]
        subject = None
        for candidate in candidates:
            subject = Subject.objects.using(alias).filter(name__iexact=candidate).first()
            if subject is not None:
                break
        if subject:
            if subject.category == "Unclassified":
                subject.category = category
            if subject.a_level_type == "N/A":
                subject.a_level_type = "Compulsory" if name == "General Paper" else "Optional"
                subject.level = "Both" if subject.o_level_type != "N/A" else "A-Level"
            subject.save(using=alias, update_fields=["category", "a_level_type", "level"])
        else:
            code = f"NCDC-AL-{index:02}"
            if Subject.objects.using(alias).filter(subject_code=code).exists():
                raise ValueError(f"Subject code {code} is already in use; resolve the conflicting code before loading the catalogue.")
            Subject.objects.using(alias).create(name=name, category=category, subject_code=code, level="A-Level",
                o_level_type="N/A", a_level_type="Compulsory" if name == "General Paper" else "Optional",
                status="Active", description="NCDC higher-secondary menu. Configure school teaching allocations and papers separately.")


# NCDC lower-secondary menu: https://ncdc.go.ug/directorates/, checked
# 2026-10-08. Individual languages and CRE/IRE are separate choices.
# Only the seven subjects compulsory throughout S1-S4 default to Compulsory.
# Configure S1-S2 additional requirements through class subject assignments.
ORDINARY_SUBJECTS = [
    ("English", "Languages"),
    ("Mathematics", "Sciences"),
    ("History & Political Education", "Arts"),
    ("Geography", "Arts"),
    ("Physics", "Sciences"),
    ("Biology", "Sciences"),
    ("Chemistry", "Sciences"),
    ("General Science", "Sciences"),
    ("Physical Education", "General"),
    ("Christian Religious Education", "Arts"),
    ("Islamic Religious Education", "Arts"),
    ("Entrepreneurship", "Arts"),
    ("Kiswahili", "Languages"),
    ("Agriculture", "Sciences"),
    ("Information Communication Technology", "Technical"),
    ("French", "Languages"),
    ("German", "Languages"),
    ("Latin", "Languages"),
    ("Arabic", "Languages"),
    ("Chinese", "Languages"),
    ("Literature in English", "Arts"),
    ("Art and Design", "Arts"),
    ("Performing Arts", "Arts"),
    ("Technology and Design", "Technical"),
    ("Nutrition & Food Technology", "Technical"),
    ("Ateso", "Languages"),
    ("Dhopadhola", "Languages"),
    ("Leb Acoli", "Languages"),
    ("Leblango", "Languages"),
    ("Luganda", "Languages"),
    ("Lugbarati", "Languages"),
    ("Lumasaaba", "Languages"),
    ("Lusoga", "Languages"),
    ("Runyoro-Rutooro", "Languages"),
    ("Runyankore-Rukiga", "Languages"),
]
ORDINARY_CORE_SUBJECTS = {name for name, _ in ORDINARY_SUBJECTS[:7]}
ORDINARY_ALIASES = {
    **ALIASES,
    "English": ["English Language"],
    "History & Political Education": ["History and Political Education"],
    "Entrepreneurship": ["Entrepreneurship Education"],
    "Literature in English": ["Literature"],
    "Information Communication Technology": ["ICT", "Information and Communication Technology", "Information & Communication Technology"],
    "Nutrition & Food Technology": ["Nutrition and Food Technology"],
}


@transaction.atomic
def load_ordinary_subjects():
    """Merge the O-Level menu without changing existing school choices."""
    period = AcademicPeriod.load()
    AcademicPeriod.objects.select_for_update().get(pk=period.pk)
    for index, (name, category) in enumerate(ORDINARY_SUBJECTS, 1):
        candidates = [name, *ORDINARY_ALIASES.get(name, [])]
        name_filter = Q()
        for candidate in candidates:
            name_filter |= Q(name__iexact=candidate)
        matches = list(Subject.objects.filter(name_filter))
        if len(matches) > 1:
            raise ValueError(f"Multiple subjects match {name}; resolve the duplicate names before loading the catalogue.")
        subject_type = "Compulsory" if name in ORDINARY_CORE_SUBJECTS else "Optional"
        if matches:
            subject = matches[0]
            if subject.category == "Unclassified":
                subject.category = category
            if subject.o_level_type == "N/A":
                subject.o_level_type = subject_type
                subject.level = "Both" if subject.a_level_type != "N/A" else "O-Level"
            subject.save(update_fields=["category", "o_level_type", "level"])
        else:
            code = f"NCDC-OL-{index:02}"
            if Subject.objects.filter(subject_code=code).exists():
                raise ValueError(f"Subject code {code} is already in use; resolve the conflicting code before loading the catalogue.")
            Subject.objects.create(
                name=name, category=category, subject_code=code, level="O-Level",
                o_level_type=subject_type, a_level_type="N/A", status="Active",
                description="NCDC lower-secondary menu. Configure class-specific compulsory/elective choices and papers separately.",
            )
