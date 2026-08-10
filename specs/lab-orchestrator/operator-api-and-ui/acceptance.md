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

## Interfaces and compatibility

- [x] **ORCH-API-AC-05:** Bearer mode protects mutations and token material stays
  out of responses; no-auth requires explicit allowed networks.
- [x] **ORCH-API-AC-06:** Requests, lists, photos, probes, and returned diagnostic
  output enforce bounds and content/path validation.

## Quality attributes

- [x] **ORCH-API-AC-07:** ASGI/unit tests cover OpenAPI, CRUD/ETags, auth/network,
  exact approval, page separation, and lab operations.
- [ ] **ORCH-API-AC-08:** Current deployed service bind/firewall/auth/token-file
  permissions and operator workflows have been audited on the live host.

## Verification evidence

- `tests.unit.test_orchestrator_web` exercises the HTTP/UI contracts and
  `tests.unit.test_orchestrator` exercises CLI-domain operations; reconciled
  2026-08-10.
- No live service security/operations audit was performed for this iteration.

## Acceptance rule

Route/security changes require ASGI tests for allowed and denied cases plus
OpenAPI compatibility. Claims about deployment exposure or background health
require live host/service evidence, not source inspection alone.
