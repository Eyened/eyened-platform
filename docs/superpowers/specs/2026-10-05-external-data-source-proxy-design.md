# External data source proxy — design

Date: 2026-10-05
Status: draft, awaiting review

## Problem

The client's extension config (`client/src/lib/extensions.ts`) adds an
"Optio" panel to study blocks in the browser (`StudyBlock.svelte:51`) and to
the viewer's visits panel (`PanelVisits.svelte:16`). It points at an absolute
URL, `http://eyened-server:5000/api/project/${project.name}/patient/${patient.identifier}/study/${study.date}`,
which `loadDataSource` (`client/src/lib/browser/dataSources.ts:21`) fetches
directly from the user's browser.

Behind HTTPS (`https://eyened.erasmusmc.nl`) the browser blocks every one of
these requests as mixed content.

The deeper problem is access control. The browser calls Optio without any
eyened session, so no RBAC applies. Today the only boundary is network
reachability of `eyened-server:5000`. Any route that lets the browser reach
Optio through the public host removes that boundary.

## Requirement

Optio data for a study is visible only to users who can see that study in
eyened, which means RS project members (and admins, per existing RBAC).

## Decision

The eyened server proxies the request. The browser asks eyened for a study's
data from a named source. eyened loads the study through the existing
RBAC-scoped repository, builds the upstream URL from the study's own fields,
calls the upstream over the internal network, and returns the JSON unchanged.

Rejected alternatives:

- **nginx `auth_request`.** eyened would have to parse Optio's URL layout to
  check access, so the rule lives in two places and breaks silently when Optio
  changes.
- **Making Optio enforce eyened RBAC.** Optio would need HTTPS, session
  forwarding and a per-request authz call to a new eyened endpoint. That puts
  the security-critical check in a second codebase, and the eyened endpoint it
  needs is as large as this proxy. Worth revisiting only if three or more
  external services need eyened's RBAC.

## Design

### Configuration

`server/config.py`, `Settings` (env prefix `EYENED_API_`):

```python
data_sources: dict[str, str] = {}
```

Env var `EYENED_API_DATA_SOURCES`: a JSON object mapping source name to an
upstream URL template. The placeholders are `{project}`, `{patient}` and
`{date}`. The default is empty, so a stock open-source install exposes nothing.
The Erasmus deployment sets:

```
EYENED_API_DATA_SOURCES={"optio": "http://eyened-server:5000/api/project/{project}/patient/{patient}/study/{date}"}
```

`deploy/compose.yaml` passes it to the server as
`EYENED_API_DATA_SOURCES: ${EYENED_API_DATA_SOURCES:-{}}`. It must be `{}`
rather than an empty default, because pydantic-settings rejects `""` for a
dict field. Both behaviours were checked: an empty value raises
`SettingsError`, and Compose renders `${V:-{}}` as `'{}'`. This follows the
existing rule in that block of restating non-string defaults instead of
writing `:-`.

`deploy/.env.example` gets a commented entry next to the other
`EYENED_API_*` variables.

### Service

`server/services/exceptions.py`: add

```python
class UpstreamError(ServiceError):
    """An external data source failed or timed out (maps to HTTP 502)."""

    status_code = 502
```

`server/services/study_service.py`: add a method to `StudyService`:

```python
def fetch_data_source(self, name: str, study_id: int) -> bytes:
```

1. Look up the template with `settings.data_sources.get(name)`. If there isn't
   one, raise `NotFoundError`.
2. Load the study with `self.repository.get_by_id(study_id)`, which is already
   RBAC-scoped. If it returns `None`, raise `NotFoundError`. This is the same
   pattern as `tag_study`, so an invisible study and a missing study look the
   same.
3. Build the URL with `template.format(project=…, patient=…, date=…)`:
   - `project` is `study.Patient.Project.ProjectName`.
   - `patient` is `study.Patient.PatientIdentifier`.
   - `date` is `study.StudyDate.isoformat()`, which gives `YYYY-MM-DD`.

   Each value goes through `urllib.parse.quote(value, safe="")`, so an
   identifier can't change the path.
4. `GET` the URL with `httpxyz.Client(timeout=10)`:
   - upstream 404: raise `NotFoundError`.
   - any other non-2xx status, a timeout or a connection error: raise
     `UpstreamError`, with a warning log naming the source and status. The
     URL isn't logged, because it contains a participant identifier.
   - 2xx: return `response.content`.

### Route

`server/routes/studies.py`, a sync handler like its neighbours:

```python
@router.get("/data-sources/{name}/studies/{study_id}")
def get_study_data_source(
    name: str,
    study_id: int,
    service: StudyService = Depends(get_study_service),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    return Response(service.fetch_data_source(name, study_id), media_type="application/json")
```

It returns the upstream bytes unparsed. The client already expects Optio's
`Record<string, row[]>` shape. No router registration is needed.

### Client

No code changes. `loadDataSource` already sends relative URLs through
`fetchApi`, which prefixes `/api` and carries the session cookie.

In `extensions.ts`, change the `optio_source_study.url` to
`/data-sources/optio/studies/${study.id}`. The `conditions` on project name
stay, so non-RS studies make no request.

### Deployment

Optio stays on `eyened-server`. The eyened server container must be able to
resolve and reach `eyened-server:5000`. If Docker's DNS can't resolve that
name, the deployment adds an `extra_hosts` entry or uses the IP in the
template. Nothing moves to the VM, and nginx doesn't change.

## Tests

Server tests follow the python-testing-patterns skill, using the existing
route-test fixtures. The upstream is faked with an `httpxyz.MockTransport`,
injected by patching where the service builds its client. There's no live
Optio.

1. A visible study returns 200 with the upstream body. The upstream received
   the URL with the project, patient and date filled in.
2. A study outside the user's projects returns 404, and the upstream is never
   called.
3. An unknown source name returns 404.
4. An upstream 500 or a timeout returns 502. An upstream 404 returns 404.
5. A patient identifier containing `/` reaches the upstream percent-encoded.

## Out of scope

- **The patient-level source** (`optio_source_patient`, "All optio data").
  It's dead config: nothing has read `extensions.browser.patient` since
  `d659b951` removed it from `PatientComponent.svelte`. Whether that removal
  was intentional is an open question for Bart/Jose. Restoring it would add a
  `/patients/{patient_id}` route with the same shape.
- **Untracking `extensions.ts`.** It's committed despite
  `client/src/lib/.gitignore`. After this change it no longer contains an
  internal hostname for the study source. Deal with it separately.
- **Caching, retries, streaming, and server-sent source lists.** The client
  already caches per URL, and there's one source.
- **Startup validation of templates.** A template with an unknown placeholder
  fails as a 500 on the first request, which is visible enough for an
  admin-set variable.
