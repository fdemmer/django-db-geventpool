"""Settings for the test suite.

tox sets DB_ENGINE (backend module), GREEN (gevent or eventlet) and
TEST_DB_NAME per env. Monkey-patching happens before Django is imported, in
the tox command (``python -m gevent.monkey --module django test``).
"""

import os

DB_ENGINE = os.environ.get("DB_ENGINE", "postgresql_psycopg3")
GREEN = os.environ.get("GREEN", "gevent")

# psycopg2 needs psycogreen to cooperate with the event loop (psycopg3 doesn't)
try:
    from psycopg2cffi import compat

    compat.register()
except ImportError:
    pass

try:
    import psycopg2  # noqa: F401
except ImportError:
    pass
else:
    if GREEN == "eventlet":
        import psycogreen.eventlet

        psycogreen.eventlet.patch_psycopg()
    else:
        import psycogreen.gevent

        psycogreen.gevent.patch_psycopg()

SECRET_KEY = "not-secret"
DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": f"django_db_geventpool.backends.{DB_ENGINE}",
        "NAME": "test",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "ATOMIC_REQUESTS": False,
        "CONN_MAX_AGE": 0,
        "HOST": "localhost",
        # tox sets a name per env, so envs can run in parallel (tox -p)
        "TEST": {"NAME": os.environ.get("TEST_DB_NAME")},
    }
}
INSTALLED_APPS = ["tests", "django_db_geventpool"]
if DB_ENGINE == "postgis":
    INSTALLED_APPS.append("tests_gis")
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
