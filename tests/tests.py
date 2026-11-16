import datetime

import gevent

from django.core.exceptions import ImproperlyConfigured
from django.db import connections
from django.test import SimpleTestCase, TestCase
from django_db_geventpool.utils import close_connection

from .models import TestModel


@close_connection
def test_multiple_connections(count):
    print("Test {0} starts".format(count))
    for x in range(0, 20):
        assert not TestModel.objects.exists()
    print("Test {0} ends".format(count))


class ModelTest(TestCase):
    databases = {"default"}

    def test_model_save(self):
        data = {
            "charfield": "testing save",
            "jsonfield": {"test": "value"},
        }
        pk = TestModel.objects.create(**data).pk

        obj = TestModel.objects.get(pk=pk)
        for key in data.keys():
            self.assertEqual(data[key], getattr(obj, key))

    def test_connections(self):
        greenlets = []

        for x in range(0, 50):
            greenlets.append(gevent.spawn(test_multiple_connections, x))
        gevent.joinall(greenlets, raise_error=True)


class TimeZoneTest(SimpleTestCase):
    """Pooled connections must use Django's time zone, whatever the server default."""

    def setUp(self):
        settings_dict = {**connections["default"].settings_dict, "CONN_MAX_AGE": 0}
        settings_dict["OPTIONS"] = {**settings_dict["OPTIONS"], "MAX_CONNS": 1}
        self.db = connections["default"].__class__(settings_dict, alias="time_zone_test")
        self.addCleanup(self.db.closeall)
        self.addCleanup(self.db.close)

    def test_reused_connection_is_utc(self):
        self.db.ensure_connection()
        with self.db.connection.cursor() as cursor:
            # what a connection gets from a server with a non-UTC default time zone
            cursor.execute("SET TIME ZONE 'Europe/Vienna'")
        self.db.close()  # back to the pool, still in Europe/Vienna

        self.db.ensure_connection()  # the same connection from the pool
        with self.db.cursor() as cursor:
            cursor.execute("SHOW TimeZone")
            self.assertEqual(cursor.fetchone()[0], "UTC")
            value = datetime.datetime(2026, 11, 15, 11, 38, 8, tzinfo=datetime.timezone.utc)
            cursor.execute("SELECT %s::timestamptz", [value])
            self.assertEqual(cursor.fetchone()[0], value)


class DjangoPoolOptionTest(SimpleTestCase):
    def test_pool_option_is_rejected(self):
        settings_dict = {**connections["default"].settings_dict}
        settings_dict["OPTIONS"] = {**settings_dict["OPTIONS"], "pool": True}
        with self.assertRaises(ImproperlyConfigured):
            connections["default"].__class__(settings_dict, alias="pool_option_test")
