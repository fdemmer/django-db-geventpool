import functools
import logging
import sys

try:
    from gevent.lock import Semaphore
except ImportError:
    from eventlet.semaphore import Semaphore

from django.core.exceptions import ImproperlyConfigured

from .creation import DatabaseCreation

logger = logging.getLogger("django.geventpool")

connection_pools_lock = Semaphore(value=1)

POOL_OPTIONS = ["MAX_CONNS", "REUSE_CONNS"]


class DatabaseWrapperMixin:
    pool_class = None
    creation_class = DatabaseCreation
    INTRANS = None
    # Not named `_connection_pools`/`pool`: since Django 5.1 the PostgreSQL backend
    # uses those for its own psycopg pool and skips setting up the connection (time
    # zone, role) and health checks whenever `pool` is set.
    _gevent_connection_pools = {}

    def __init__(self, *args, **kwargs):
        self._gevent_pool = None
        super().__init__(*args, **kwargs)
        if self.settings_dict["OPTIONS"].get("pool"):
            raise ImproperlyConfigured(
                "django-db-geventpool can't be combined with Django's connection "
                "pool, remove the 'pool' option."
            )
        self.creation = self.creation_class(self)

    @property
    def gevent_pool(self):
        if self._gevent_pool is not None:
            return self._gevent_pool
        with connection_pools_lock:
            if self.alias not in self._gevent_connection_pools:
                options = self.settings_dict["OPTIONS"]
                pool_options = {key: options[key] for key in POOL_OPTIONS if key in options}
                self._gevent_pool = self.pool_class(
                    **self.get_connection_params(), **pool_options
                )
                self._gevent_connection_pools[self.alias] = self._gevent_pool
            else:
                self._gevent_pool = self._gevent_connection_pools[self.alias]
        return self._gevent_pool

    def get_new_connection(self, conn_params: dict):
        if self.connection is None:
            # New connections are created by the backend (e.g. to set the isolation
            # level, register PostGIS adapters with psycopg3).
            create = functools.partial(super().get_new_connection, conn_params)
            self.connection = self.gevent_pool.get(create=create)
            self.closed_in_transaction = False
        return self.connection

    def get_connection_params(self) -> dict:
        conn_params = super().get_connection_params()
        for key in POOL_OPTIONS:
            conn_params.pop(key, None)
        return conn_params

    def close(self):
        self.validate_thread_sharing()
        if self.closed_in_transaction or self.connection is None:
            return  # no need to close anything
        try:
            self._close()
        except:
            self.gevent_pool.discard(self.connection)
            # In some cases (database restart, network connection lost etc...)
            # the connection to the database is lost without giving Django a
            # notification. If we don't set self.connection to None, the error
            # will occur at every request.
            self.connection = None
            logger.warning(
                "psycopg error while closing the connection.", exc_info=sys.exc_info()
            )
            raise
        finally:
            self.set_clean()

    def close_if_unusable_or_obsolete(self):
        # Always close the connection because it's not (usually) really being closed.
        self.close()

    def _close(self):
        if self.connection.closed:
            self.gevent_pool.discard(self.connection)
            self.gevent_pool.close()
        else:
            if self.connection.info.transaction_status == self.INTRANS:
                self.connection.rollback()
                self.connection.autocommit = True
            with self.wrap_database_errors:
                self.gevent_pool.put(self.connection)
        self.connection = None

    def closeall(self):
        for pool in self._gevent_connection_pools.values():
            pool.close()

    def set_clean(self):
        if self.in_atomic_block:
            self.closed_in_transaction = True
            self.needs_rollback = True
