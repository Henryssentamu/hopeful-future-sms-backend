from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from .catalogue import SUBJECTS, load_advanced_subjects
from .models import Subject, SubjectPaper


class AdvancedCatalogueTests(TestCase):
    def test_menu_is_complete_repeatable_and_preserves_existing_papers(self):
        maths = Subject.objects.create(subject_code="MATH", name="Mathematics", level="O-Level", o_level_type="Compulsory", a_level_type="N/A")
        paper = SubjectPaper.objects.create(subject=maths, paper="Paper 1", label="Existing school paper")
        load_advanced_subjects()
        load_advanced_subjects()
        self.assertEqual(len(SUBJECTS), 40)
        self.assertEqual(Subject.objects.count(), 40)
        maths.refresh_from_db()
        self.assertEqual(maths.level, "Both")
        self.assertEqual(maths.subject_code, "MATH")
        self.assertEqual(maths.category, "Sciences")
        self.assertTrue(SubjectPaper.objects.filter(pk=paper.pk, subject=maths).exists())
        maths.category = "General"
        maths.save()
        load_advanced_subjects()
        maths.refresh_from_db()
        self.assertEqual(maths.category, "General")

    def test_category_filter_and_catalogue_permissions(self):
        client = APIClient()
        user = get_user_model().objects.create_user(username="catalogue-teacher", role="TEACHER")
        client.force_authenticate(user)
        self.assertEqual(client.post("/api/academics/subjects/load-advanced-catalogue/").status_code, 403)
        user.role = "DOS"
        user.save()
        self.assertEqual(client.post("/api/academics/subjects/load-advanced-catalogue/").status_code, 200)
        response = client.get("/api/academics/subjects/?category=Sciences")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["results"])
        self.assertTrue(all(s["category"] == "Sciences" for s in response.data["results"]))


class OrdinaryCatalogueTests(TestCase):
    def test_repeatable_menu_preserves_shared_subjects_and_school_choices(self):
        from .catalogue import load_ordinary_subjects
        load_advanced_subjects()
        maths = Subject.objects.get(name="Mathematics")
        paper = SubjectPaper.objects.create(subject=maths, paper="Paper 1", label="School paper")
        load_ordinary_subjects()
        count = Subject.objects.count()
        maths.refresh_from_db()
        self.assertEqual(maths.level, "Both")
        self.assertEqual(maths.o_level_type, "Compulsory")
        maths.category = "General"
        maths.status = "Inactive"
        maths.o_level_type = "Optional"
        maths.save()
        load_ordinary_subjects()
        self.assertEqual(Subject.objects.exclude(o_level_type="N/A").count(), 35)
        self.assertEqual(Subject.objects.count(), count)
        maths.refresh_from_db()
        self.assertEqual((maths.category, maths.status, maths.o_level_type), ("General", "Inactive", "Optional"))
        self.assertTrue(SubjectPaper.objects.filter(pk=paper.pk).exists())
        self.assertEqual(Subject.objects.get(name="History").o_level_type, "N/A")
        self.assertEqual(Subject.objects.get(name="History & Political Education").level, "O-Level")
        self.assertEqual(Subject.objects.get(name="Principal ICT").o_level_type, "N/A")

    def test_code_conflict_rolls_back_entire_load(self):
        from .catalogue import load_ordinary_subjects
        Subject.objects.create(name="School special", subject_code="NCDC-OL-35", level="A-Level", o_level_type="N/A", a_level_type="Optional")
        with self.assertRaises(ValueError):
            load_ordinary_subjects()
        self.assertEqual(Subject.objects.count(), 1)

    def test_api_permissions_and_catalogue_content(self):
        client = APIClient()
        user = get_user_model().objects.create_user(username="ordinary-catalogue", role="TEACHER")
        client.force_authenticate(user)
        url = "/api/academics/subjects/load-ordinary-catalogue/"
        self.assertEqual(client.post(url).status_code, 403)
        for role in ("DOS", "ADMIN", "HEADMASTER"):
            user.role = role
            user.save()
            self.assertEqual(client.post(url).status_code, 200)
        self.assertEqual(Subject.objects.count(), 35)
        self.assertEqual(Subject.objects.filter(o_level_type="Compulsory").count(), 7)
