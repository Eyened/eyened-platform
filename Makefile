# Thin aliases for developers. Every target's logic lives in deploy/scripts/
# or install.sh, so that nothing on the client path needs make: `make` is
# absent on Windows, ships with the Xcode Command Line Tools on macOS, and is
# a separate package on minimal Linux images.
#
# See deploy/README.md for what each of these does.

#
# The Makefile does not know which compose binary this host has, and must not
# learn it at parse time: a `COMPOSE := $(shell …)` would run on every make
# invocation including `make help`, and would expand to the EMPTY STRING when
# docker is missing — turning `make down` into `cd deploy && down`. Targets
# call deploy/scripts/dc.sh, which resolves the binary when it actually runs.
#
# REPO_ROOT is derived from the Makefile's own path via $(MAKEFILE_LIST), NOT
# `$(shell git rev-parse --show-toplevel)`. That call runs at parse time on
# EVERY invocation too, including `make help`, and 'git' is not guaranteed —
# a downloaded release tarball (no .git) or a host without git installed both
# turn it into the empty string, which is the exact same 'cd  && …' footgun
# the DC comment above warns about, just moved one line up. $(MAKEFILE_LIST)
# needs neither git nor a subprocess: make already knows where this file is.

SHELL := /bin/sh
REPO_ROOT := $(patsubst %/,%,$(dir $(abspath $(lastword $(MAKEFILE_LIST)))))
DEPLOY := $(REPO_ROOT)/deploy
DC := $(DEPLOY)/scripts/dc.sh

PY := python3
OPENAPI_DIR := $(REPO_ROOT)/client/src/types
OPENAPI_JSON := $(OPENAPI_DIR)/openapi.json
OPENAPI_TS := $(REPO_ROOT)/client/src/types/openapi.ts

.PHONY: install doctor up down logs prod migrate db-shell \
        gen-openapi gen-types gen-client-types

## install: the client install (production stack, bundled database). Alias for ./install.sh.
install:
	$(REPO_ROOT)/install.sh

## doctor: preflight checks without building anything.
doctor:
	$(DEPLOY)/scripts/doctor.sh dev

## up: the developer stack — hot reload, source mounted, bundled database.
up:
	$(DEPLOY)/scripts/stack.sh dev

## down: stop this stack.
down:
	$(DC) down

## logs: follow logs.
logs:
	$(DC) logs -f

## prod: a site deployment against an EXTERNAL database.
prod:
	$(DEPLOY)/scripts/stack.sh prod

## migrate: apply pending migrations inside the server container.
# Interactive on purpose: alembic's own confirmation prompt still guards
# manual runs against a populated database.
#
# NOT `alembic -c orm/migrations/alembic.ini upgrade head`: alembic.ini's
# script_location is a path relative to the process CWD, not to the ini file,
# so that form resolves against /app and fails with "FAILED: Path doesn't
# exist" on stdout (rc=255) instead of running. `cd` into the migrations
# directory first, the same shape bootstrap.sh uses.
migrate:
	$(DC) exec -it server sh -c 'cd orm/migrations && alembic upgrade head'

## db-shell: a MySQL shell in the bundled database.
db-shell:
	$(DC) exec -it database sh -c 'exec mysql -u"$$MYSQL_USER" -p"$$MYSQL_PASSWORD" "$$MYSQL_DATABASE"'

gen-openapi:
	$(PY) $(REPO_ROOT)/dev/generate_openapi.py $(OPENAPI_DIR)

gen-types: gen-openapi
	npx --yes openapi-typescript@7 $(OPENAPI_JSON) -o $(OPENAPI_TS)

gen-client-types: gen-types
	@echo "Types generated at $(OPENAPI_TS)"
