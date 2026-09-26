import threading
from datetime import date

from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TransactionTestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role

from .models import RecruitmentRecord, RecruitmentStatus, StaffType, Teacher


class RecruitmentConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.hr = get_user_model().objects.create_user(username="hr", password="pass", role=Role.HR)
        self.candidate = RecruitmentRecord.objects.create(
            candidate_name="Grace Teacher", staff_type=StaffType.TEACHING, role="Mathematics",
            email="grace@example.com", phone="0700", applied_date=date(2026, 1, 1),
        )

    def test_hire_is_idempotent_under_concurrent_requests(self):
        barrier = threading.Barrier(2)
        statuses = []

        def hire():
            close_old_connections()
            client = APIClient()
            client.force_authenticate(get_user_model().objects.get(pk=self.hr.pk))
            barrier.wait()
            response = client.post(f"/api/staff/recruitment/{self.candidate.pk}/hire/")
            statuses.append(response.status_code)
            close_old_connections()

        threads = [threading.Thread(target=hire) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(statuses), [201, 409])
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.status, RecruitmentStatus.HIRED)
        self.assertIsNotNone(self.candidate.hired_user_id)
        self.assertEqual(Teacher.objects.filter(user_id=self.candidate.hired_user_id).count(), 1)

    def test_rejected_candidate_cannot_be_hired(self):
        self.candidate.status = RecruitmentStatus.REJECTED
        self.candidate.save(update_fields=["status"])
        client = APIClient()
        client.force_authenticate(self.hr)
        response = client.post(f"/api/staff/recruitment/{self.candidate.pk}/hire/")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Teacher.objects.count(), 0)
