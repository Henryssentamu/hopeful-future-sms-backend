import os
from collections.abc import Mapping, Sequence
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured


VALID_ENVIRONMENTS = {"development", "test", "production"}
PRODUCTION_REQUIRED_VARIABLES = (
    "DJANGO_DEBUG",
    "DJANGO_SECRET_KEY",
    "DJANGO_ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
    "DB_HOST",
    "DB_PORT",
    "REDIS_HOST",
    "REDIS_PORT",
    "REDIS_CACHE_DB",
    "REDIS_CELERY_DB",
    "DJANGO_TRUST_PROXY_SSL_HEADER",
    "DRF_NUM_PROXIES",
    "DJANGO_SECURE_HSTS_SECONDS",
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    "DJANGO_SECURE_HSTS_PRELOAD",
)


def get_environment() -> str:
    environment = os.getenv("DJANGO_ENVIRONMENT", "development").strip().lower()
    if environment not in VALID_ENVIRONMENTS:
        choices = ", ".join(sorted(VALID_ENVIRONMENTS))
        raise ImproperlyConfigured(f"DJANGO_ENVIRONMENT must be one of: {choices}.")
    return environment


def env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ImproperlyConfigured(f"{name} must be a boolean value such as True or False.")


def env_int(name: str, default: int, *, minimum: int = 0) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        value = int(raw_value.strip())
    except (TypeError, ValueError) as exc:
        raise ImproperlyConfigured(f"{name} must be an integer.") from exc
    if value < minimum:
        raise ImproperlyConfigured(f"{name} must be at least {minimum}.")
    return value


def env_csv(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


def _is_placeholder(value: str) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in ("change-me", "changeme", "replace-with", "dev-only"))


def _is_reserved_hostname(hostname: str) -> bool:
    normalized = hostname.lower().lstrip(".").rstrip(".")
    return normalized in {"localhost", "127.0.0.1", "::1"} or normalized.endswith(
        (".example", ".invalid", ".localhost", ".test")
    )


def _validate_allowed_hosts(allowed_hosts: Sequence[str], errors: list[str]) -> None:
    if not allowed_hosts:
        errors.append("DJANGO_ALLOWED_HOSTS must contain the production backend hostname.")
        return

    for host in allowed_hosts:
        if host == "*":
            errors.append("DJANGO_ALLOWED_HOSTS must not use the '*' wildcard in production.")
        elif ":" in host or "/" in host:
            errors.append("DJANGO_ALLOWED_HOSTS entries must be hostnames without a scheme, port, or path.")
        elif _is_reserved_hostname(host):
            errors.append("DJANGO_ALLOWED_HOSTS must not contain localhost or a reserved example hostname.")


def _validate_https_origins(name: str, origins: Sequence[str], errors: list[str]) -> None:
    if not origins:
        errors.append(f"{name} must contain the production frontend HTTPS origin.")
        return

    for origin in origins:
        try:
            parsed = urlsplit(origin)
            parsed_port = parsed.port
        except ValueError:
            errors.append(f"{name} contains an invalid origin.")
            continue

        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
            or _is_reserved_hostname(parsed.hostname)
        ):
            errors.append(
                f"{name} entries must be real HTTPS origins without credentials, paths, queries, or fragments."
            )
        elif parsed_port is not None and not 1 <= parsed_port <= 65535:
            errors.append(f"{name} contains an invalid port.")


def _validate_positive_integer(
    environment_variables: Mapping[str, str],
    name: str,
    errors: list[str],
    *,
    allow_zero: bool,
) -> None:
    minimum = 0 if allow_zero else 1
    try:
        value = int(environment_variables.get(name, ""))
        if value < minimum:
            raise ValueError
    except ValueError:
        qualifier = "zero or a positive integer" if allow_zero else "a positive integer"
        errors.append(f"{name} must be {qualifier}.")


def _validate_throttle_rates(throttle_rates: Mapping[str, object], errors: list[str]) -> None:
    accepted_periods = {
        "s",
        "sec",
        "second",
        "seconds",
        "m",
        "min",
        "minute",
        "minutes",
        "h",
        "hour",
        "hours",
        "d",
        "day",
        "days",
    }
    for scope, raw_rate in throttle_rates.items():
        rate = str(raw_rate)
        try:
            count, period = rate.split("/", maxsplit=1)
            if int(count) < 1 or period.lower() not in accepted_periods:
                raise ValueError
        except ValueError:
            errors.append(
                f"Authentication throttle rate '{scope}' must use a positive value such as 5/minute or 100/hour."
            )


def validate_production_configuration(
    *,
    environment_variables: Mapping[str, str],
    debug: bool,
    secret_key: str,
    allowed_hosts: Sequence[str],
    cors_allowed_origins: Sequence[str],
    csrf_trusted_origins: Sequence[str],
    database_settings: Mapping[str, object],
    secure_hsts_seconds: int,
    throttle_rates: Mapping[str, object],
) -> None:
    errors: list[str] = []
    database_cache = environment_variables.get("DJANGO_CACHE_BACKEND", "redis").strip().lower() == "database"
    required_variables = [
        name for name in PRODUCTION_REQUIRED_VARIABLES
        if not (database_cache and name.startswith("REDIS_"))
    ]
    missing = [name for name in required_variables if not environment_variables.get(name, "").strip()]
    if missing:
        errors.append(f"Missing required environment variables: {', '.join(missing)}.")

    if debug:
        errors.append("DJANGO_DEBUG must be False in production.")

    if (
        len(secret_key) < 50
        or len(set(secret_key)) < 5
        or secret_key.startswith("django-insecure-")
        or _is_placeholder(secret_key)
    ):
        errors.append("DJANGO_SECRET_KEY must be a strong, unique value of at least 50 characters.")

    _validate_allowed_hosts(allowed_hosts, errors)
    _validate_https_origins("CORS_ALLOWED_ORIGINS", cors_allowed_origins, errors)
    _validate_https_origins("CSRF_TRUSTED_ORIGINS", csrf_trusted_origins, errors)
    if not set(cors_allowed_origins).issubset(csrf_trusted_origins):
        errors.append("Every CORS_ALLOWED_ORIGINS entry must also appear in CSRF_TRUSTED_ORIGINS.")

    database_name = str(database_settings.get("NAME", "")).strip()
    database_user = str(database_settings.get("USER", "")).strip()
    database_password = str(database_settings.get("PASSWORD", ""))
    database_host = str(database_settings.get("HOST", "")).strip()
    database_port = str(database_settings.get("PORT", "")).strip()
    if not all((database_name, database_user, database_password, database_host, database_port)):
        errors.append("DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, and DB_PORT must all be set in production.")
    if database_user.lower() == "root":
        errors.append("DB_USER must be a least-privilege application account, not root.")
    if (
        len(database_password) < 20
        or len(set(database_password)) < 5
        or _is_placeholder(database_password)
        or database_password.lower() in {"hfss", "hfss_root", "password"}
    ):
        errors.append("DB_PASSWORD must be a unique production value of at least 20 characters.")
    try:
        port_number = int(database_port)
        if not 1 <= port_number <= 65535:
            raise ValueError
    except ValueError:
        errors.append("DB_PORT must be an integer between 1 and 65535.")

    if not database_cache:
        _validate_positive_integer(environment_variables, "REDIS_PORT", errors, allow_zero=False)
        _validate_positive_integer(environment_variables, "REDIS_CACHE_DB", errors, allow_zero=True)
        _validate_positive_integer(environment_variables, "REDIS_CELERY_DB", errors, allow_zero=True)
    _validate_throttle_rates(throttle_rates, errors)

    if secure_hsts_seconds < 3600:
        errors.append("DJANGO_SECURE_HSTS_SECONDS must be at least 3600 in production.")

    if errors:
        formatted_errors = "\n".join(f"- {error}" for error in errors)
        raise ImproperlyConfigured(f"Unsafe production configuration:\n{formatted_errors}")
