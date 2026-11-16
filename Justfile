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

test env="":
    uvx --with tox-uv tox {{ if env == "" { "--parallel auto" } else { "-e " + env } }}

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
