import datetime

from django.core.exceptions import ImproperlyConfigured
from django.db import connections, transaction
from django.db.backends.postgresql.psycopg_any import IsolationLevel
from django.test import SimpleTestCase, TestCase
from django_db_geventpool.utils import close_connection

from .models import TestModel

try:
    import gevent

    def run_concurrently(func, count):
        greenlets = [gevent.spawn(func, x) for x in range(count)]
        gevent.joinall(greenlets, raise_error=True)

except ImportError:
    import eventlet

    def run_concurrently(func, count):
        list(eventlet.GreenPool(count).imap(func, range(count)))


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
        run_concurrently(test_multiple_connections, 50)


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


class IsolationLevelTest(SimpleTestCase):
    """Connections created by the pool must use the isolation level from OPTIONS."""

    databases = {"default"}
    alias = "isolation_level_test"

    def setUp(self):
        settings_dict = {**connections["default"].settings_dict}
        settings_dict["OPTIONS"] = {
            **settings_dict["OPTIONS"],
            "isolation_level": IsolationLevel.SERIALIZABLE,
        }
        db = connections["default"].__class__(settings_dict, alias=self.alias)
        connections[self.alias] = db
        self.addCleanup(connections.__delitem__, self.alias)
        self.addCleanup(db.closeall)
        self.addCleanup(db.close)

    def test_isolation_level(self):
        with transaction.atomic(using=self.alias):
            with connections[self.alias].cursor() as cursor:
                cursor.execute("SHOW transaction_isolation")
                self.assertEqual(cursor.fetchone()[0], "serializable")


class PoolTestCase(SimpleTestCase):
    """Runs against a private wrapper whose pool holds a single connection."""

    databases = {"default"}

    def setUp(self):
        self.alias = f"pool_test_{self._testMethodName}"
        settings_dict = {**connections["default"].settings_dict, "CONN_MAX_AGE": 0}
        settings_dict["OPTIONS"] = {**settings_dict["OPTIONS"], "MAX_CONNS": 1}
        self.db = connections["default"].__class__(settings_dict, alias=self.alias)
        connections[self.alias] = self.db
        self.addCleanup(connections.__delitem__, self.alias)
        self.addCleanup(self.db._gevent_connection_pools.pop, self.alias, None)
        self.addCleanup(self.db.closeall)
        self.addCleanup(self.db.close)

    def backend_pid(self):
        self.db.ensure_connection()
        return self.db.connection.info.backend_pid

    def terminate(self, pid):
        """Kill a backend from the server side, like a database restart would."""
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT pg_terminate_backend(%s, 5000)", [pid])
            self.assertIs(cursor.fetchone()[0], True)


class DeadConnectionTest(PoolTestCase):
    def test_dead_connection_is_replaced(self):
        pid = self.backend_pid()
        self.db.close()  # back to the pool
        self.terminate(pid)

        # check_usable fails on the pooled connection, so a new one is created
        self.assertNotEqual(self.backend_pid(), pid)
        with self.db.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)
        self.assertEqual(self.db.gevent_pool.size, 1)


class CloseInTransactionTest(PoolTestCase):
    def test_open_transaction_is_rolled_back(self):
        pid = self.backend_pid()
        self.db.connection.autocommit = False
        with self.db.connection.cursor() as cursor:
            cursor.execute("SET application_name = 'dirty'")
        self.assertEqual(self.db.connection.info.transaction_status, self.db.INTRANS)
        self.db.close()

        self.assertEqual(self.backend_pid(), pid)  # the same connection, reused
        self.assertIs(self.db.connection.autocommit, True)
        with self.db.cursor() as cursor:
            cursor.execute("SHOW application_name")
            self.assertNotEqual(cursor.fetchone()[0], "dirty")

    def test_close_in_atomic_block(self):
        with transaction.atomic(using=self.alias):
            TestModel.objects.using(self.alias).create(charfield="rolled back")
            self.db.close()
            self.assertIs(self.db.closed_in_transaction, True)
            self.assertIs(self.db.needs_rollback, True)
            self.db.close()  # no-op until the atomic block is left
        self.assertIsNone(self.db.connection)

        self.assertFalse(TestModel.objects.using(self.alias).exists())


class CloseErrorTest(PoolTestCase):
    def test_error_while_closing(self):
        # the server drops the connection while it is in a transaction, so the
        # rollback in close() fails
        pid = self.backend_pid()
        self.db.connection.autocommit = False
        with self.db.connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        self.terminate(pid)

        with self.assertLogs("django.geventpool", "WARNING"):
            with self.assertRaises(self.db.Database.Error):
                self.db.close()
        self.assertIsNone(self.db.connection)

        self.assertNotEqual(self.backend_pid(), pid)

    def test_close_closed_connection(self):
        pid = self.backend_pid()
        self.db.connection.close()  # closed outside of the pool
        self.db.close()
        self.assertIsNone(self.db.connection)

        self.assertNotEqual(self.backend_pid(), pid)
