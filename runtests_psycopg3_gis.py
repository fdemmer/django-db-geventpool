#!/usr/bin/env python
import os
import sys
import gevent.monkey

gevent.monkey.patch_all()

import django
from django.conf import settings
from django.test.runner import DiscoverRunner


settings.configure(
    DEBUG=True,
    DATABASES={
        "default": {
            "ENGINE": "django_db_geventpool.backends.postgis",
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
        "tests_gis",
        "django_db_geventpool",
    ),
    USE_TZ=True,
    DEFAULT_AUTO_FIELD="django.db.models.BigAutoField",
)

django.setup()

test_runner = DiscoverRunner(verbosity=2)

failures = test_runner.run_tests(["tests.tests", "tests_gis.tests"])
if failures:
    sys.exit(failures)
