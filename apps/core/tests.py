import os
import subprocess
import sys
from unittest.mock import patch

from django.conf import settings
from django.core.cache.backends.db import DatabaseCache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError, connection
from django.test import Client, SimpleTestCase, TransactionTestCase, override_settings
from redis.exceptions import ConnectionError as RedisConnectionError
from rest_framework.test import APIRequestFactory

from apps.accounts.throttles import LoginUsernameThrottle


PRODUCTION_ENVIRONMENT = {
    "DJANGO_ENVIRONMENT": "production",
    "DJANGO_DEBUG": "False",
    "DJANGO_SECRET_KEY": "phase28-production-test-secret-7yR2kP9mQ4vN8xC6aL3sW5dF1hJ0",
    "DJANGO_ALLOWED_HOSTS": "api.hopefulfuture-school.ug",
    "CORS_ALLOWED_ORIGINS": "https://portal.hopefulfuture-school.ug",
    "CSRF_TRUSTED_ORIGINS": "https://portal.hopefulfuture-school.ug",
    "DB_NAME": "hopeful_future_sms",
    "DB_USER": "hopeful_future_app",
    "DB_PASSWORD": "phase28-production-test-database-password-8Kp4vN2mQ7",
    "DB_HOST": "mysql",
    "DB_PORT": "3306",
    "REDIS_HOST": "redis",
    "REDIS_PORT": "6379",
    "REDIS_CACHE_DB": "1",
    "REDIS_CELERY_DB": "0",
    "DJANGO_TRUST_PROXY_SSL_HEADER": "True",
    "DRF_NUM_PROXIES": "1",
    "DJANGO_SECURE_HSTS_SECONDS": "31536000",
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
    "DJANGO_SECURE_HSTS_PRELOAD": "True",
}


class EnvironmentProfileTests(SimpleTestCase):
    def run_manage(self, *arguments: str, overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment.update(PRODUCTION_ENVIRONMENT)
        if overrides:
            environment.update(overrides)
        return subprocess.run(
            [sys.executable, "manage.py", *arguments],
            cwd=settings.BASE_DIR,
            env=environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def assert_configuration_error(self, variable: str, **overrides: str) -> None:
        result = self.run_manage("check", overrides=overrides)
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("Unsafe production configuration", output)
        self.assertIn(variable, output)

    def test_development_profile_preserves_local_http_operation(self):
        result = self.run_manage(
            "shell",
            "-c",
            (
                "from django.conf import settings; "
                "assert settings.ENVIRONMENT == 'development'; "
                "assert settings.DEBUG; "
                "assert not settings.SECURE_SSL_REDIRECT; "
                "assert not settings.SESSION_COOKIE_SECURE; "
                "assert not settings.CSRF_COOKIE_SECURE"
            ),
            overrides={
                "DJANGO_ENVIRONMENT": "development",
                "DJANGO_DEBUG": "True",
                "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1",
                "CORS_ALLOWED_ORIGINS": "http://localhost:8080",
                "CSRF_TRUSTED_ORIGINS": "http://localhost:8080,http://127.0.0.1:8080",
                "DJANGO_TRUST_PROXY_SSL_HEADER": "False",
                "DRF_NUM_PROXIES": "0",
                "DJANGO_SECURE_HSTS_SECONDS": "0",
                "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
                "DJANGO_SECURE_HSTS_PRELOAD": "False",
            },
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_complete_production_profile_passes_strict_django_security_checks(self):
        result = self.run_manage("check", "--deploy", "--tag", "security", "--fail-level", "WARNING")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("System check identified no issues", result.stdout)

    def test_staged_hsts_profile_reports_only_the_two_documented_advisories(self):
        result = self.run_manage(
            "check",
            "--deploy",
            "--tag",
            "security",
            overrides={
                "DJANGO_SECURE_HSTS_SECONDS": "3600",
                "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
                "DJANGO_SECURE_HSTS_PRELOAD": "False",
            },
        )
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(output.count("?: (security."), 2, output)
        self.assertIn("security.W005", output)
        self.assertIn("security.W021", output)

    def test_database_cache_profile_does_not_require_redis(self):
        result = self.run_manage("check", overrides={
            "DJANGO_CACHE_BACKEND": "database",
            "CELERY_TASK_ALWAYS_EAGER": "True",
            "REDIS_HOST": "", "REDIS_PORT": "",
            "REDIS_CACHE_DB": "", "REDIS_CELERY_DB": "",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_database_cache_profile_rejects_background_workers(self):
        result = self.run_manage("check", overrides={
            "DJANGO_CACHE_BACKEND": "database", "CELERY_TASK_ALWAYS_EAGER": "False",
        })
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires CELERY_TASK_ALWAYS_EAGER=True", result.stderr)

    def test_unknown_cache_backend_is_rejected(self):
        result = self.run_manage("check", overrides={"DJANGO_CACHE_BACKEND": "local-memory"})
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DJANGO_CACHE_BACKEND must be redis or database", result.stderr)

    def test_production_rejects_debug_mode(self):
        self.assert_configuration_error("DJANGO_DEBUG", DJANGO_DEBUG="True")

    def test_production_rejects_placeholder_secret(self):
        self.assert_configuration_error("DJANGO_SECRET_KEY", DJANGO_SECRET_KEY="change-me-in-production")

    def test_production_rejects_weak_database_credentials(self):
        self.assert_configuration_error("DB_PASSWORD", DB_PASSWORD="hfss")

    def test_production_rejects_non_https_frontend_origins(self):
        self.assert_configuration_error(
            "CORS_ALLOWED_ORIGINS",
            CORS_ALLOWED_ORIGINS="http://portal.hopefulfuture-school.ug",
        )

    def test_production_requires_an_explicit_proxy_count(self):
        result = self.run_manage("check", overrides={"DRF_NUM_PROXIES": ""})
        output = result.stdout + result.stderr

        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("DRF_NUM_PROXIES", output)

    def test_production_rejects_invalid_redis_configuration(self):
        self.assert_configuration_error("REDIS_PORT", REDIS_PORT="not-a-port")

    def test_production_rejects_invalid_authentication_throttle_rates(self):
        self.assert_configuration_error(
            "Authentication throttle rate",
            AUTH_LOGIN_IP_THROTTLE_RATE="many/sometimes",
        )


class ProductionSeedSafetyTests(SimpleTestCase):
    @override_settings(IS_PRODUCTION=True)
    def test_demo_seeding_is_disabled_before_accessing_data(self):
        with self.assertRaisesMessage(
            CommandError,
            "Demo data seeding is disabled when DJANGO_ENVIRONMENT=production.",
        ):
            call_command("seed_demo_data", verbosity=0)


@override_settings(
    ALLOWED_HOSTS=["api.hopefulfuture-school.ug"],
    CORS_ALLOWED_ORIGINS=["https://portal.hopefulfuture-school.ug"],
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
    SECURE_HSTS_SECONDS=3600,
)
class ProductionTransportTests(SimpleTestCase):
    def setUp(self):
        self.client = Client()

    def test_plain_http_redirects_to_https(self):
        response = self.client.get(
            "/admin/login/",
            HTTP_HOST="api.hopefulfuture-school.ug",
        )

        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], "https://api.hopefulfuture-school.ug/admin/login/")

    def test_trusted_forwarded_https_avoids_redirect_loop_and_sets_hsts(self):
        response = self.client.get(
            "/admin/login/",
            HTTP_HOST="api.hopefulfuture-school.ug",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Strict-Transport-Security"], "max-age=3600")

    def test_allowed_frontend_origin_receives_cors_preflight_header(self):
        response = self.client.options(
            "/api/auth/login/",
            HTTP_HOST="api.hopefulfuture-school.ug",
            HTTP_ORIGIN="https://portal.hopefulfuture-school.ug",
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Access-Control-Allow-Origin"], "https://portal.hopefulfuture-school.ug")

    @override_settings(DEBUG=False)
    def test_unlisted_backend_host_is_rejected(self):
        response = self.client.get(
            "/admin/login/",
            HTTP_HOST="unexpected.hopefulfuture-school.ug",
            HTTP_X_FORWARDED_PROTO="https",
        )

        self.assertEqual(response.status_code, 400)


@override_settings(SECURE_SSL_REDIRECT=True)
class HealthProbeTests(SimpleTestCase):
    def test_liveness_works_without_authentication_or_dependencies(self):
        response = self.client.get("/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertIn("no-store", response["Cache-Control"])

    def test_probes_reject_writes(self):
        for path in ("/health/live/", "/health/ready/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 405)

    def test_readiness_checks_both_dependencies(self):
        with patch("config.health.connections") as databases, patch("config.health.cache") as cache:
            cache.get.return_value = "ok"
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)
        cursor = databases["default"].cursor.return_value.__enter__.return_value
        cursor.execute.assert_called_once_with("SELECT 1")
        cache.set.assert_called_once()
        cache.get.assert_called_once()
        cache.delete.assert_called_once()

    def test_dependency_failures_return_503_without_disclosing_details(self):
        failures = (
            ("database", OperationalError("private database details")),
            ("redis", RedisConnectionError("private redis details")),
        )
        for dependency, failure in failures:
            with self.subTest(dependency=dependency):
                with patch("config.health.connections") as databases, patch("config.health.cache") as cache:
                    if dependency == "database":
                        databases["default"].cursor.side_effect = failure
                    else:
                        cache.set.side_effect = failure
                    response = self.client.get("/health/ready/")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"status": "unavailable"})
                self.assertIn("no-store", response["Cache-Control"])

    def test_readiness_detects_a_cache_that_drops_writes(self):
        with patch("config.health.connections"), patch("config.health.cache") as cache:
            cache.get.return_value = None
            response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {"status": "unavailable"})

    def test_normal_routes_still_require_https(self):
        self.assertEqual(self.client.get("/api/auth/me/").status_code, 301)


@override_settings(CACHES={"default": {
    "BACKEND": "django.core.cache.backends.db.DatabaseCache",
    "LOCATION": "test_operational_cache",
}})
class DatabaseCacheHostingTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        call_command("createcachetable", verbosity=0)

    @classmethod
    def tearDownClass(cls):
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP TABLE test_operational_cache")
        finally:
            super().tearDownClass()

    def test_readiness_uses_real_database_cache(self):
        response = self.client.get("/health/ready/")
        self.assertEqual(response.status_code, 200)

    def test_login_limits_are_shared_across_cache_instances(self):
        factory = APIRequestFactory()
        request = factory.post("/api/auth/login/", {}, format="json")
        request.data = {"username": "cpanel-shared-limit"}
        first = LoginUsernameThrottle()
        second = LoginUsernameThrottle()
        first.cache = DatabaseCache("test_operational_cache", {})
        second.cache = DatabaseCache("test_operational_cache", {})
        first.num_requests = second.num_requests = 1
        self.assertTrue(first.allow_request(request, None))
        self.assertFalse(second.allow_request(request, None))
