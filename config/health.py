"""Minimal operational probes; never expose dependency exceptions or records."""

from uuid import uuid4

from django.core.cache import cache
from django.db import DatabaseError, connections
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe
from redis.exceptions import RedisError


@never_cache
@require_safe
def live(request):
    return JsonResponse({"status": "ok"})


@never_cache
@require_safe
def ready(request):
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        key = f"health:{uuid4().hex}"
        cache.set(key, "ok", timeout=10)
        available = cache.get(key) == "ok"
        cache.delete(key)
        if not available:
            return JsonResponse({"status": "unavailable"}, status=503)
    except (DatabaseError, RedisError):
        return JsonResponse({"status": "unavailable"}, status=503)
    return JsonResponse({"status": "ok"})
