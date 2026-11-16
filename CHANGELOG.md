# Changelog

## Unreleased

- Released as `fdemmer-django-db-geventpool`, a fork of [django-db-geventpool](https://github.com/jneight/django-db-geventpool); the import path and backend names are unchanged, uninstall `django-db-geventpool` first
- Built with setuptools; added a Justfile to test, build and publish; the CI workflow is renamed to `main.yml` and the publish workflow to `publish.yml`, which builds with uv and uses pinned actions
- Fixed pooled connections keeping the server's time zone and ignoring `assume_role` on Django >= 5.1: `DatabaseWrapper.pool` (renamed to `gevent_pool`) and `_connection_pools` (renamed to `_gevent_connection_pools`) shadowed Django's native pool, which made Django skip setting up connections and health checks
- The `pool` option now raises `ImproperlyConfigured`, as the native pool can't be combined with the gevent pool; `'pool': False` is no longer needed
- Fixed geometry adapters missing on new pooled PostGIS connections with psycopg3 (`cannot adapt type 'PostGISAdapter'`) and the `isolation_level` option being ignored: new connections are created with the backend's `get_new_connection` again, [#98](https://github.com/jneight/django-db-geventpool/issues/98)
- Test with Django 4.2, 5.2, 6.0 and 6.1 (dropped 5.0 and 5.1) and Python up to 3.15, updated classifiers
- Dropped support for Python 3.8, which is end-of-life (the setuptools versions needed to build the package require Python >= 3.9)
- CI runs the tox envs (one job per env) with tox-uv instead of separate workflows per driver, with pinned actions and PostGIS image
- Support running the tests in parallel (`tox -p`) with a test database per env
- Fixed the psycopg3 test runners on Python >= 3.12 (`distutils`), and the GIS envs also running the non-GIS tests
- Updated `docker-compose.yml` to PostGIS 18

## 4.0.8

- Support for Django 5.1, disable Django's native pool with `'pool': False` in `OPTIONS`, [#93](https://github.com/jneight/django-db-geventpool/issues/93), [#94](https://github.com/jneight/django-db-geventpool/issues/94)
- Pool connections are created with `connect()` of the driver again instead of the backend's `get_new_connection` (reverts 4.0.7)
- Renamed `DatabaseConnectionPool.closeall()` to `close()`
- Dropped support for Django < 4.2
- Tests for Django 5.0, 5.1 and Python 3.13

## 4.0.7

- Create pool connections with the backend's `get_new_connection`, so the PostGIS backend registers its geometry adapters with psycopg3, [#89](https://github.com/jneight/django-db-geventpool/issues/89), @kneirinck

## 4.0.6

- Fixed `ImportError` when using the PostGIS backend, [#85](https://github.com/jneight/django-db-geventpool/issues/85)
- Tests for the PostGIS backend with psycopg2 and psycopg3

## 4.0.5

- Fixed package: the psycopg3 backend's `__init__.py` was misnamed, [#84](https://github.com/jneight/django-db-geventpool/issues/84)

## 4.0.4

- Fix package

## 4.0.3

- Support for psycopg3

## 4.0.2

- Fixed eventlet rlock using as context manager, issue [#73](https://github.com/jneight/django-db-geventpool/issues/73), @StuBz211

## 4.0.1

- Changed JSONField to come from `django.db.models` instead of the removed (as of Django 4.0) `django.contrib.postgres.fields`, @veracrux

## 4.0.0

- Support for django 4.0

## 3.2.3

- Fixed TypeError when using JSONField with Django 3.1, @bvallant

## 3.2.2

- Add "wait" option to prevent more than MAX_CONNS being created at the same time, @bellini666

## 3.2.0

- Removed support for django < 1.11
- Updated previous deprecation warnings
- Improved queue and connection handling, @coderanger

## 3.1.0

- Correct connection cleanup after disabling autocommit with `transaction.setautocommit(False)`

## 3.0.1

- Fix setup.py UnicodeDecodeError when installing with python 3.6

## 3.0.0

- psycopg2 is not installed by default, @mattbriancon

## 2

- Testing: Add support for Python 3 and Django 2, @stefankoegl
- Fixed error with undefined attribute "closed_in_transaction", @bmunoz89
- Working with django 1.11 LTS and 2.0

## Previous versions:

- Proper error handling for integer types, @gxx
- Ensure that close_connection property closes, even in the case of an error, @gxx
- Compatible with Python 3, @sumitalp
- Fixed self.pool must exist, @rajivm
- Fixed Postgis pool connection, @rajivm
