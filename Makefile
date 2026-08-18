REPO_ROOT := $(shell git rev-parse --show-toplevel)
PY := python3
OPENAPI_DIR := $(REPO_ROOT)/client/src/types
OPENAPI_TS := $(REPO_ROOT)/client/src/types/openapi.ts

.PHONY: gen-openapi gen-types gen-client-types

gen-openapi:
	$(PY) $(REPO_ROOT)/dev/generate_openapi.py $(OPENAPI_DIR)

gen-types: gen-openapi
	npm --prefix client run generate:api

gen-client-types: gen-types
	@echo "Types generated at $(OPENAPI_TS)"
