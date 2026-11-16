# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

A Django database backend for PostgreSQL/PostGIS that pools connections with gevent (eventlet as a fallback). Users set `ENGINE` to one of `django_db_geventpool.backends.{postgresql_psycopg3,postgresql_psycopg2,postgis}` and set `MAX_CONNS`/`REUSE_CONNS` in `OPTIONS`. Supports Django 4.2, 5.2, 6.0 and 6.1 on Python 3.9–3.15 (see `tox.ini` for the exact matrix). The distribution is published as `fdemmer-django-db-geventpool`, but the import name is still `django_db_geventpool` (see Fork and Build and release below).

## Tests

The tests need a running PostgreSQL with PostGIS on localhost:5432 (user and password `postgres`):

    docker compose up -d                          # or: just db

Run them through tox with tox-uv, the same way CI does (`just test` / `just test <env>` wraps this):

    uvx --with tox-uv tox -l                      # list envs
    uvx --with tox-uv tox run -e py312-dj52-pg3   # one env
    uvx --with tox-uv tox run -e py312-dj52-pg3-gis
    uvx --with tox-uv tox -p                      # all envs in parallel

- Env names follow `py3X-djNN-pg{2,3}[-gis]`. The `pg2`/`pg3` factor picks psycopg2-binary or psycopg3. The `gis` factor uses the `postgis` engine, runs both `tests` and `tests_gis`, and needs GDAL/GEOS installed locally.
- Each env runs one of the `runtests_psycopg{2,3}[_gis].py` scripts. Each script monkey-patches with gevent (the psycopg2 scripts also apply psycogreen), configures settings inline and runs `DiscoverRunner` on hardcoded labels. tox passes no positional args, so to run a single test, change the label list in the script for that run or run the script directly in an env's virtualenv (e.g. `.tox/py312-dj52-pg3/bin/python runtests_psycopg3.py`).
- `TEST_DB_NAME` (set by tox per env) gives each env its own test database so that `tox -p` works. `PG*` env vars are passed through.
- CI (`.github/workflows/main.yml`) runs one job per tox env against the `postgis/postgis` service.

## Architecture

- `backends/base.py`: `DatabaseWrapperMixin` holds the core logic. Each concrete backend is `DatabaseWrapper(DatabaseWrapperMixin, <Django's DatabaseWrapper>)` and sets `pool_class` and `INTRANS` (the driver's in-transaction status constant).
  - One pool per DB alias lives in the class-level dict `_gevent_connection_pools`, which is created lazily behind a semaphore by the `gevent_pool` property.
  - **Don't name anything `pool` or `_connection_pools`.** Since Django 5.1 the PostgreSQL backend uses those names for its native psycopg pool and skips connection setup (time zone, role) and health checks when they are set. Setting Django's `pool` option raises `ImproperlyConfigured`.
  - `get_new_connection` takes a connection from the pool. It passes the backend's own `super().get_new_connection` as the `create` callable, so new connections get backend-specific setup (isolation level, PostGIS adapters with psycopg3). This has flip-flopped across releases (4.0.7 → 4.0.8 → unreleased); see CHANGELOG and issues #89 and #98 before changing it.
  - `close()` / `close_if_unusable_or_obsolete()` always return the connection to the pool (rolling back an open transaction) instead of really closing it. `closeall()` closes every pool and is used by `creation.py` before the test DB is destroyed.
  - `get_connection_params` strips `MAX_CONNS`/`REUSE_CONNS` before they reach the driver.
- `backends/pool.py`: `DatabaseConnectionPool` is a driver-agnostic queue-based pool, adapted from gevent's psycopg2 pool example. Connections are tracked in a `WeakSet`. `reuse` sets the queue size and `maxsize` caps the total. `check_usable` (`SELECT 1`) runs on reuse and the connection is replaced on `DBERROR`.
- `backends/postgresql_psycopg{2,3}/base.py`: the driver-specific `PostgresConnectionPool` (`DBERROR`, `connect`, `check_usable`) plus the wrapper. These two files are near-duplicates, so keep them in sync.
- `backends/postgis/base.py`: uses psycopg3 if it can be imported, otherwise psycopg2, and reuses that driver's pool class.
- `utils.py`: the `close_connection` decorator, which sends `request_finished` so that greenlets spawned outside requests return their connections.

## Fork

This is a fork of upstream [jneight/django-db-geventpool](https://github.com/jneight/django-db-geventpool) (remote `upstream`). The fork lives at `fdemmer/django-db-geventpool` (remote `origin`). Work happens on `fdemmer/*` branches that are merged into the fork's `master`. Fixes are also meant to go back upstream. The fork is released separately on PyPI as `fdemmer-django-db-geventpool`, starting at 5.0. Upstream's latest release is `django-db-geventpool` 4.0.8.

Changes since the fork (merge-base `986782a`). The `## Unreleased` section of `CHANGELOG.md` has the user-facing details:

- **Test matrix and CI:** tox covers Django 4.2/5.2/6.0/6.1 and Python up to 3.15. The four per-driver workflows (`ci_psycopg{2,3}[_gis].yml`) are replaced by one `main.yml` that runs every tox env as its own job via tox-uv. Each env gets its own test DB so that `tox -p` works. The psycopg3 runners no longer fail on Python ≥ 3.12 (`distutils`), and docker-compose uses PostGIS 18.
- **Pool name clash (Django ≥ 5.1):** `pool` and `_connection_pools` were renamed to `gevent_pool` and `_gevent_connection_pools`. The `pool` option now raises `ImproperlyConfigured`.
- **New connections (#98, branch `fdemmer/fix-postgis-adapters`):** connections are created via the backend's `get_new_connection` again, which fixes PostGIS adapters with psycopg3 and the `isolation_level` option. Tests were added for the time zone, isolation level, the `pool` option and PostGIS geometries (`tests_gis/`).
- **Packaging and releases:** the distribution is renamed to `fdemmer-django-db-geventpool`. It is built with setuptools, published by the `publish.yml` workflow and released with a Justfile.
- README and CHANGELOG fixes (missing 4.0.5–4.0.8 entries were added). Upstream's README typo fix (#95) was picked up. Upstream's `.github/FUNDING.yml` (`a6c9aab`) is not in the fork.

To see the current state:

    git fetch upstream
    git log --oneline upstream/master..HEAD     # fork-only commits
    git log --oneline HEAD..upstream/master     # upstream commits not in the fork

## Conventions

- Add user-facing changes to `CHANGELOG.md` under `## Unreleased`. Link upstream issues/PRs as `[#NN](https://github.com/jneight/django-db-geventpool/issues/NN)`.

## Build and release

- **Version:** `__version__ = "X.Y"` in `django_db_geventpool/__init__.py` is the only place the version is set. It must stay a literal, so setuptools reads it via `attr` without importing the package. Write pre-releases as PEP 440 strings (`5.1rc1`).
- **Build:** setuptools (≥ 77, for the `license` expression; don't add license classifiers) reads the version via `[tool.setuptools.dynamic] version = {attr = "django_db_geventpool.__version__"}`. `MANIFEST.in` keeps `tests/` and `tests_gis/` out of the sdist and adds `CHANGELOG.md`. The wheel holds only `django_db_geventpool`.
- **Justfile:**
  - `just build`: `uv build` plus `twine check`
  - `just clean`
  - `just publish-test`: upload to TestPyPI
  - `just publish`: upload with `twine -r fdemmer-django-db-geventpool`, the `~/.pypirc` section; aborts on a dirty tree
  - `just gha-update`: update the pinned action SHAs
- **CI publishing:** `.github/workflows/publish.yml` runs on published or edited GitHub releases in the `release` environment. It runs `uv build` and `twine check`, then `pypa/gh-action-pypi-publish` with the `PYPI_API_TOKEN` secret. All actions are SHA-pinned.
- **Releasing:**
  1. Make a commit "Prepare release X" that only sets `__version__` and renames `## Unreleased` in `CHANGELOG.md` to `## X`.
  2. Tag it with the bare version (`5.0`, no `v`; older upstream tags use `vX.Y.Z`).
  3. Publish a GitHub release from the tag.
