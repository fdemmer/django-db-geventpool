[private]
default:
    @just --list --unsorted

gha-update:
    uvx gha-update

clean:
    rm -rf build dist
    rm -rf *.egg-info

# start PostgreSQL with PostGIS for the tests
db:
    docker compose up -d

# all envs in parallel, or one env with optional test labels
test env="" *labels:
    uvx --with tox-uv tox {{ if env == "" { "--parallel auto" } else { "-e " + env + " -- " + labels } }}

# run all envs, combine their coverage; the HTML report shows which envs ran each line
test_coverage:
    uvx coverage erase
    RUN_COVERAGE='-m coverage run --concurrency={env:GREEN} --context={env_name}' \
        uvx --with tox-uv tox --parallel auto
    uvx coverage combine
    uvx coverage report
    uvx coverage html
    @echo "open htmlcov/index.html, click a line's context marker to see the envs"

build: clean
    uv build
    uvx twine check --strict dist/*

publish-test: build
    uvx twine upload -r testpypi dist/*

publish: build
    #!/usr/bin/env bash
    status=$(git status --porcelain)
    if [ -z "$status" ]; then
        uvx twine upload -r fdemmer-django-db-geventpool dist/*
    else
        echo "Aborting upload: working directory is dirty" >&2
        exit 1
    fi
