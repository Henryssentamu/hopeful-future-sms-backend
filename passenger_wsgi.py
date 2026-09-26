"""Namecheap/cPanel entry point; configure production values before restart."""

import os

os.environ.setdefault("DJANGO_ENVIRONMENT", "production")
os.environ.setdefault("DJANGO_DEBUG", "False")
os.environ.setdefault("DJANGO_CACHE_BACKEND", "database")
os.environ.setdefault("CELERY_TASK_ALWAYS_EAGER", "True")

from config.wsgi import application  # noqa: E402,F401
