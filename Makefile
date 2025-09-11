REPO_ROOT := $(shell git rev-parse --show-toplevel)
PY := python3
OPENAPI_DIR := $(REPO_ROOT)/docs/src/content/docs/api
OPENAPI_JSON := $(OPENAPI_DIR)/openapi.json
OPENAPI_TS := $(REPO_ROOT)/client/src/types/openapi.ts

.PHONY: gen-openapi gen-types gen-client-types

gen-openapi:
	$(PY) $(REPO_ROOT)/dev/generate_openapi.py $(OPENAPI_DIR)

gen-types: gen-openapi
	npx --yes openapi-typescript@7 $(OPENAPI_JSON) -o $(OPENAPI_TS)

gen-client-types: gen-types
	@echo "Types generated at $(OPENAPI_TS)"
