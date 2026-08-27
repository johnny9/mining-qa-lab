# Operator API and UI — acceptance

## Functional behavior

- [x] **ORCH-API-AC-01:** API exposes versioned config/resources, gate triggers,
  PR approval, history/control, and lab probe/preflight routes in OpenAPI.
- [x] **ORCH-API-AC-02:** Configuration mutations require authorization,
  matching ETag, and full validation before persistence.
- [x] **ORCH-API-AC-03:** Gate/PR actions bind the selected gate/repository and
  exact commit/head identity.
- [x] **ORCH-API-AC-04:** Focused overview/gates/lab/trigger/config pages render
  from server-side snapshot/history rather than independent policy state.
- [x] **ORCH-API-AC-09:** Manual UI/API accepts a project, compatible gate,
  optional exact commit or branch, and device types; blank source resolves the
  latest configured `main`, then `master`, to an exact commit.
- [x] **ORCH-API-AC-10:** Authenticated run history lists archived artifacts,
  views bounded UTF-8 files, and downloads files without exposing storage paths.
- [x] **ORCH-API-AC-11:** Overview offers a confirmed retry only for failed,
  errored, or cancelled runs and invokes the authenticated retry API, which
  requeues incomplete assignments without rerunning passed assignments.
- [x] **ORCH-API-AC-12:** Hybrid pages expose local gate editing/runs and
  separate Status-owned shared definitions. A locally authenticated shared run
  is forwarded with the bound Lab token and can target only that Lab.
- [x] **ORCH-API-AC-13:** The Run page lists every matching bounded open PR
  regardless of contributor trust classification, retains exact-head
  confirmation, and lets the operator select a non-empty subset of the gate's
  configured Testcode modules for local or shared execution.
- [x] **ORCH-API-AC-14:** Open PR presentation shows at most ten cards per page,
  reports the visible range and page count, and keeps exact SHA, contributor,
  branches, confirmation, and run action visible in a compact layout.
- [x] **ORCH-API-AC-15:** Contributor filtering applies to the complete loaded
  PR set before pagination, resets to page one, and reports matching versus
  total counts without changing exact-SHA approval.

## Interfaces and compatibility

- [x] **ORCH-API-AC-05:** Bearer mode protects mutations and token material stays
  out of responses; no-auth requires explicit allowed networks.
- [x] **ORCH-API-AC-06:** Requests, lists, photos, probes, and returned diagnostic
  output enforce bounds and content/path validation.

## Quality attributes

- [x] **ORCH-API-AC-07:** ASGI/unit tests cover OpenAPI, CRUD/ETags, auth/network,
  exact approval, page separation, retry eligibility/action, and lab operations.
- [ ] **ORCH-API-AC-08:** Current deployed service bind/firewall/auth/token-file
  permissions and operator workflows have been audited on the live host.

## Verification evidence

- `tests.unit.test_orchestrator_web` exercises authenticated HTTP/UI retry
  behavior and `tests.unit.test_orchestrator` covers server-rendered retry
  eligibility alongside CLI-domain operations; reconciled 2026-08-10.
- No live service security/operations audit was performed for this iteration.

## Acceptance rule

Route/security changes require ASGI tests for allowed and denied cases plus
OpenAPI compatibility. Claims about deployment exposure or background health
require live host/service evidence, not source inspection alone.
