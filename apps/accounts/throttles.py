import hashlib
import hmac
from collections.abc import Mapping

from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle


class LoginIPThrottle(SimpleRateThrottle):
    """Limits aggregate login traffic from one trusted client address."""

    scope = "login_ip"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class LoginUsernameThrottle(SimpleRateThrottle):
    """Limits repeated login attempts against one username across addresses."""

    scope = "login_username"

    def get_cache_key(self, request, view):
        if not isinstance(request.data, Mapping):
            return None

        username = request.data.get("username")
        if not isinstance(username, str) or not username.strip():
            return None

        username_digest = hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            username.strip().encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": username_digest,
        }


class TokenRefreshIPThrottle(LoginIPThrottle):
    """Limits refresh-token traffic separately from interactive login."""

    scope = "token_refresh_ip"
