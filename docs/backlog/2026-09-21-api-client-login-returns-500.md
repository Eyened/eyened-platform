# `POST /api/auth/login` with `api_client: true` returns 500, and it is the documented path for scripts

- **Source:** Diátaxis triage of the API documentation, 2026-09-21. A code defect found by a
  documentation review; verified against source and by probing a replica of the model and payload.

**Status:** open

## What

`server/routes/auth.py:236` declares `@router.post("/auth/login", response_model=UserResponse)`.
The `api_client` branch at `:250-257` returns:

```python
{"user": …, "access_token": …, "refresh_token": …, "token_type": "bearer", "expires_in": …}
```

`UserResponse` (`:64-68`) requires top-level `id`, `username`, `role`. FastAPI serialises the
return value through the response model, so this raises `ResponseValidationError` → **HTTP 500**.
Probed on a replica: `3 validation errors: ('response','id') missing, ('response','username')
missing, ('response','role') missing`. `client/src/types/openapi.json` agrees the 200 is a bare
`UserResponse`.

Nothing in `server/` or `client/` exercises `api_client: true` — it appears only at `auth.py:61`
(the request model), `auth.py:250` (this branch), and `client/src/types/openapi.ts:2524`
(generated) — so **no test covers it**.

## Why

`api/index.mdx:17` and `api/authentication.mdx:23-24` offer `api_client: true` as the way a script
authenticates, presented as an equal alternative to `POST /api/auth/token`. Every integrator who
follows the documentation hits a 500 on their first call.

Two fixes, and they are independent:

1. **Code** — either drop `response_model` from the route and declare the union properly, or make
   the `api_client` branch return a model that satisfies it. Needs a test either way; that test is
   the point, since the absence of one is why this survived.
2. **Docs** — point scripts at `POST /api/auth/token`, which genuinely returns `TokenResponse`, and
   drop the `api_client` claim. Tracked in
   `2026-09-21-docs-factual-defects-triage.md`; do not fix the docs to describe a 500.
