from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from apps.academics.models import SchoolClass
from .models import Student


class StudentPhotoTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.settings_override = override_settings(MEDIA_ROOT=self.directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.user = get_user_model().objects.create_user(username="photo-dos", role="DOS")
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.school_class = SchoolClass.objects.create(name="Photo class", level_group="Senior 1", level="O-Level", stream="A")

    def register(self, upload):
        return self.client.post("/api/students/", {"student_number": "PHOTO-1", "name": "Photo Learner",
            "school_class": self.school_class.pk, "gender": "Female", "enrollment_date": "2026-10-01", "photo": upload}, format="multipart")

    def test_device_upload_is_normalized_and_private(self):
        image = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(image, format="PNG")
        response = self.register(SimpleUploadedFile("portrait.png", image.getvalue(), content_type="image/png"))
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data["has_photo"])
        self.assertNotIn("photo_file", response.data)
        student = Student.objects.get(pk=response.data["id"])
        self.assertTrue(student.photo_file.name.endswith(".jpg"))
        url = f"/api/students/{student.pk}/photo/"
        photo = self.client.get(url)
        self.assertEqual(photo.status_code, 200)
        self.assertEqual(photo["Content-Type"], "image/jpeg")
        self.assertEqual(photo["Cache-Control"], "private, no-store")
        self.assertTrue(b"".join(photo.streaming_content).startswith(b"\xff\xd8"))
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(url).status_code, 401)
        for role in ["BURSAR", "HR", "TEACHER"]:
            user = get_user_model().objects.create_user(username=f"photo-{role}", role=role)
            self.client.force_authenticate(user)
            self.assertIn(self.client.get(url).status_code, [403, 404])

    def test_disguised_file_is_rejected_without_student_creation(self):
        response = self.register(SimpleUploadedFile("portrait.jpg", b"<script>not an image</script>", content_type="image/jpeg"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Student.objects.count(), 0)

    def test_oversize_upload_is_rejected(self):
        response = self.register(SimpleUploadedFile("large.jpg", b"x" * (5 * 1024 * 1024 + 1), content_type="image/jpeg"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Student.objects.count(), 0)
