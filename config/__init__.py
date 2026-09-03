# Inside Docker, requirements.txt installs the real mysqlclient (MySQLdb)
# and this is a no-op. On a host machine without the system headers needed
# to compile mysqlclient, requirements-local.txt installs PyMySQL instead —
# shim it in as MySQLdb so Django's mysql backend works unmodified either way.
try:
    import MySQLdb  # noqa: F401
except ImportError:
    import pymysql

    pymysql.install_as_MySQLdb()

from .celery import app as celery_app  # noqa: E402,F401

__all__ = ("celery_app",)
