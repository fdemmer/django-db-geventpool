#!/usr/bin/env python
import os
import sys
import eventlet

eventlet.monkey_patch()

try:
    from psycopg2cffi import compat

    compat.register()
except ImportError:
    pass

import psycogreen.eventlet

psycogreen.eventlet.patch_psycopg()

# this env tests the eventlet fallback, fail if gevent is installed anyway
try:
    import gevent  # noqa: F401
except ImportError:
    pass
else:
    sys.exit("gevent is installed, the eventlet fallback would not be used")

import django
from django.conf import settings
from django.test.runner import DiscoverRunner


settings.configure(
    DEBUG=True,
    DATABASES={
        "default": {
            "ENGINE": "django_db_geventpool.backends.postgresql_psycopg2",
            "NAME": "test",
            "USER": "postgres",
            "PASSWORD": "postgres",
            "ATOMIC_REQUESTS": False,
            "CONN_MAX_AGE": 0,
            "HOST": "localhost",
            # tox sets a name per env, so envs can run in parallel (tox -p)
            "TEST": {"NAME": os.environ.get("TEST_DB_NAME")},
        }
    },
    INSTALLED_APPS=(
        "tests",
        "django_db_geventpool",
    ),
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)
django.setup()

from django_db_geventpool import utils
from django_db_geventpool.backends import pool

assert pool.RLock is utils.NullContextRLock, pool.RLock

test_runner = DiscoverRunner(verbosity=2)

failures = test_runner.run_tests(["tests.tests"])
if failures:
    sys.exit(failures)
