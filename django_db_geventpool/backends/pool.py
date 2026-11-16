# this file is a modified version of the psycopg2 used at gevent examples
# to be compatible with django, also checks if
# DB connection is closed and reopen it:
# https://github.com/surfly/gevent/blob/master/examples/psycopg2_pool.py
import logging
import weakref

logger = logging.getLogger("django.geventpool")

try:
    from gevent import queue
    from gevent.lock import RLock
except ImportError:
    from eventlet import queue
    from ..utils import NullContextRLock as RLock


class DatabaseConnectionPool:
    DBERROR = None
    # seconds to wait for a returned connection before checking for a free slot
    WAIT_TIMEOUT = 1

    def __init__(self, maxsize: int = 100, reuse: int = 100):
        # Use a WeakSet here so, even if we fail to discard the connection
        # when it is being closed, or it is closed outside of here, the item
        # will be removed automatically
        self._conns = weakref.WeakSet()
        # slots held by connections that are being created
        self._creating = 0
        self.maxsize = maxsize
        self.pool = queue.Queue(maxsize=max(reuse, 1))
        self.lock = RLock()

    @property
    def size(self):
        with self.lock:
            return len(self._conns)

    def get(self, create):
        """Return a pooled connection, or a new one from ``create()``.

        At most ``maxsize`` connections exist at a time. When all of them are
        in use, wait for one to be returned to the pool.
        """
        while True:
            if self._reserve():
                logger.debug("DB connection queue empty, creating a new one")
                return self._create(create)
            try:
                # wake up now and then in case a slot was freed without a put(),
                # e.g. by a failed create() or a discarded connection
                conn = self.pool.get(timeout=self.WAIT_TIMEOUT)
            except queue.Empty:
                continue

            try:
                # check connection is still valid
                self.check_usable(conn)
                logger.debug("DB connection reused")
                return conn
            except self.DBERROR:
                logger.debug("DB connection was closed, creating a new one")
                with self.lock:
                    # hand the dead connection's slot to its replacement
                    self._conns.discard(conn)
                    self._creating += 1
                return self._create(create)

    def _reserve(self):
        """Reserve a slot for a new connection if none is idle and one is free."""
        with self.lock:
            if self.pool.empty() and len(self._conns) + self._creating < self.maxsize:
                self._creating += 1
                return True
            return False

    def _create(self, create):
        """Create a connection in a slot reserved by ``_reserve()``."""
        conn = None
        try:
            conn = create()
            return conn
        finally:
            with self.lock:
                self._creating -= 1
                if conn is not None:
                    self._conns.add(conn)

    def put(self, item):
        try:
            self.pool.put_nowait(item)
            logger.debug("DB connection returned to the pool")
        except queue.Full:
            item.close()
            self.discard(item)

    def discard(self, conn):
        """Stop counting a connection that won't be returned to the pool."""
        with self.lock:
            self._conns.discard(conn)

    def close(self):
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
            except queue.Empty:
                continue
            try:
                conn.close()
            except Exception:
                continue
            finally:
                self.discard(conn)

        logger.debug("DB connections all closed")

