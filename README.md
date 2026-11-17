django-db-geventpool
====================

[![CI](https://github.com/fdemmer/django-db-geventpool/actions/workflows/main.yml/badge.svg)](https://github.com/fdemmer/django-db-geventpool/actions/workflows/main.yml)
[![pypi version](https://img.shields.io/pypi/v/fdemmer-django-db-geventpool.svg)](https://pypi.org/project/fdemmer-django-db-geventpool/)
[![pypi license](https://img.shields.io/pypi/l/fdemmer-django-db-geventpool.svg)](https://pypi.org/project/fdemmer-django-db-geventpool/)

A Django database backend for PostgreSQL and PostGIS that pools connections
between greenlets. Use it when Django runs on gevent (e.g. gunicorn's gevent
workers), where every concurrent request would otherwise open its own
connection: the pool caps the number of connections per process and keeps
some of them open for reuse.

This is a fork of [django-db-geventpool](https://github.com/jneight/django-db-geventpool),
released as `fdemmer-django-db-geventpool`. The import path and backend names are
the same as upstream's, so uninstall `django-db-geventpool` before installing it:

```
$ pip uninstall django-db-geventpool
$ pip install fdemmer-django-db-geventpool
```


Requirements
------------

- Python >= 3.9
- Django 4.2, 5.2, 6.0 or 6.1
- PostgreSQL (or PostGIS) with psycopg3 or psycopg2
- gevent (recommended) or eventlet


Installation
------------

### psycopg3 (recommended)

```
$ pip install fdemmer-django-db-geventpool gevent "psycopg[binary]"
```

psycopg3 cooperates with gevent's monkey-patching, so no extra patching is
needed. gunicorn's gevent worker monkey-patches on startup; if you start
gevent yourself, call `gevent.monkey.patch_all()` before importing Django.

### psycopg2

```
$ pip install fdemmer-django-db-geventpool gevent psycopg2-binary psycogreen
```

psycopg2 must be patched with [psycogreen](https://pypi.org/project/psycogreen/)
before the pool is used. With [gunicorn](https://gunicorn.org/), a good place is
the [`post_fork`](https://docs.gunicorn.org/en/latest/settings.html#post-fork)
hook in the config file:

```python
from psycogreen.gevent import patch_psycopg     # with gevent workers
# from psycogreen.eventlet import patch_psycopg  # with eventlet workers

def post_fork(server, worker):
    patch_psycopg()
    worker.log.info("Made psycopg2 green")
```

### eventlet

If gevent is not installed, the pool falls back to eventlet. The fallback is
tested with psycopg2 only, and eventlet itself recommends migrating away from it,
so prefer gevent for new projects.


Settings
--------

Set `ENGINE` to one of:

| Driver                | `ENGINE`                                            |
|-----------------------|-----------------------------------------------------|
| psycopg3              | `django_db_geventpool.backends.postgresql_psycopg3` |
| psycopg2              | `django_db_geventpool.backends.postgresql_psycopg2` |
| PostGIS               | `django_db_geventpool.backends.postgis` (psycopg3 if installed, psycopg2 otherwise) |

and configure the pool in `OPTIONS`:

| Option        | Default       | Meaning                                                  |
|---------------|---------------|----------------------------------------------------------|
| `MAX_CONNS`   | 4             | Maximum number of connections per process                |
| `REUSE_CONNS` | `MAX_CONNS`   | How many idle connections are kept open for reuse        |

Also:

- Set `CONN_MAX_AGE` to `0` (Django's default). Connections are kept open by the
  pool, not by Django's persistent connections.
- Don't set Django's `pool` option (Django >= 5.1). Django's native pool can't
  be combined with this one, and setting it raises `ImproperlyConfigured`.

```python
DATABASES = {
    "default": {
        "ENGINE": "django_db_geventpool.backends.postgresql_psycopg3",
        "NAME": "db",
        "USER": "postgres",
        "PASSWORD": "postgres",
        "CONN_MAX_AGE": 0,
        "OPTIONS": {
            "MAX_CONNS": 20,
            "REUSE_CONNS": 10,
        },
    }
}
```


How the pool works
------------------

- Each process has one pool per database alias, so the most connections a
  deployment opens is `processes × MAX_CONNS` per alias. With gunicorn, that is
  the number of workers times `MAX_CONNS`.
- A greenlet takes a connection from the pool when it first uses the database
  and returns it when Django closes the connection, at the end of the request.
  An open transaction is rolled back when the connection is returned.
- When all `MAX_CONNS` connections are in use, a greenlet that needs one waits
  until another greenlet returns one. There is no timeout.
- When a connection is returned and `REUSE_CONNS` idle connections are already
  waiting, it is closed. So under load up to `MAX_CONNS` connections are open,
  and when idle `REUSE_CONNS` stay open.
- Before an idle connection is reused, it is checked with `SELECT 1`. A
  connection that was dropped (e.g. by a database restart) is replaced.


Using the ORM outside requests
------------------------------

Django closes database connections, and so returns them to the pool, when a
request finishes. Code that runs outside a request, like greenlets you spawn
yourself or celery tasks, keeps its connection instead of returning it to the
pool. Such connections still count towards `MAX_CONNS`, so the pool can run dry
and requests have to wait.

Make sure each such function returns its connection when it ends. The
`close_connection` decorator is the simplest way:

```python
from django_db_geventpool.utils import close_connection

@close_connection
def foo_func():
    ...
```

It sends Django's `request_finished` signal, which you can also send yourself:

```python
from django.core.signals import request_finished

def foo_func():
    ...
    request_finished.send(sender="greenlet")
```

or call `close_old_connections()`:

```python
from django.db import close_old_connections

def foo_func():
    ...
    close_old_connections()
```


Django's native pool
--------------------

Since Django 5.1, the PostgreSQL backend can pool connections itself with
psycopg3's pool (the `pool` option in `OPTIONS`). That pool is built for threads
and is the better choice for sync or threaded workers. Use this package when
running on gevent or eventlet. The two can't be combined.


Development
-----------

The tests need PostgreSQL with PostGIS on `localhost:5432` (user and password
`postgres`) and run through tox:

```
$ docker compose up -d
$ uvx --with tox-uv tox -l                      # list envs
$ uvx --with tox-uv tox run -e py312-dj52-pg3   # one env
$ uvx --with tox-uv tox -p                      # all envs in parallel
```

The `gis` envs also need GDAL and GEOS installed.

See the [changelog](https://github.com/fdemmer/django-db-geventpool/blob/master/CHANGELOG.md)
for what changed in each release.
