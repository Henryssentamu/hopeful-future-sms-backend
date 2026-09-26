from unittest.mock import patch

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.state import token_backend

from .models import Role, User
from .throttles import LoginIPThrottle, LoginUsernameThrottle, TokenRefreshIPThrottle


@override_settings(
    CACHES={
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "authentication-throttle-tests",
        }
    }
)
class AuthenticationThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.rate_patches = [
            patch.object(LoginIPThrottle, "rate", "2/minute", create=True),
            patch.object(LoginUsernameThrottle, "rate", "2/minute", create=True),
            patch.object(TokenRefreshIPThrottle, "rate", "2/minute", create=True),
            patch.object(token_backend, "signing_key", "phase-27-test-signing-key-with-safe-length"),
        ]
        for rate_patch in self.rate_patches:
            rate_patch.start()
            self.addCleanup(rate_patch.stop)
        self.user = User.objects.create_user(
            username="protected-user",
            password="StrongPassword123!",
            role=Role.ADMIN,
        )

    def tearDown(self):
        cache.clear()

    def test_successful_login_contract_is_unchanged(self):
        response = self.client.post(
            reverse("auth-login"),
            {"username": self.user.username, "password": "StrongPassword123!"},
            format="json",
            REMOTE_ADDR="10.0.0.1",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertEqual(response.data["user"]["id"], self.user.id)
        self.assertEqual(response.data["user"]["role"], Role.ADMIN)

    def test_repeated_attempts_against_one_username_are_throttled_across_addresses(self):
        payload = {"username": self.user.username, "password": "wrong-password"}

        first = self.client.post(reverse("auth-login"), payload, format="json", REMOTE_ADDR="10.0.0.1")
        second = self.client.post(reverse("auth-login"), payload, format="json", REMOTE_ADDR="10.0.0.2")
        blocked = self.client.post(reverse("auth-login"), payload, format="json", REMOTE_ADDR="10.0.0.3")

        self.assertEqual(first.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("detail", blocked.data)
        self.assertIn("Retry-After", blocked)

    def test_login_ip_throttle_does_not_trust_forwarded_addresses_by_default(self):
        login_url = reverse("auth-login")

        first = self.client.post(
            login_url,
            {"username": "unknown-one", "password": "wrong-password"},
            format="json",
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="198.51.100.1",
        )
        second = self.client.post(
            login_url,
            {"username": "unknown-two", "password": "wrong-password"},
            format="json",
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="198.51.100.2",
        )
        blocked = self.client.post(
            login_url,
            {"username": "unknown-three", "password": "wrong-password"},
            format="json",
            REMOTE_ADDR="10.0.0.10",
            HTTP_X_FORWARDED_FOR="198.51.100.3",
        )

        self.assertEqual(first.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", blocked)

    def test_non_object_login_payload_returns_controlled_validation_error(self):
        response = self.client.post(
            reverse("auth-login"),
            ["not", "an", "object"],
            format="json",
            REMOTE_ADDR="10.0.0.30",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_requests_are_throttled_separately(self):
        refresh_url = reverse("auth-refresh")
        payload = {"refresh": "not-a-valid-token"}

        first = self.client.post(refresh_url, payload, format="json", REMOTE_ADDR="10.0.0.20")
        second = self.client.post(refresh_url, payload, format="json", REMOTE_ADDR="10.0.0.20")
        blocked = self.client.post(refresh_url, payload, format="json", REMOTE_ADDR="10.0.0.20")

        self.assertEqual(first.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(second.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(blocked.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("detail", blocked.data)
        self.assertIn("Retry-After", blocked)
