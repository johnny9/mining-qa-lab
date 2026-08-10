# Parent gate publication — acceptance

## Functional behavior

- [x] **ORCH-PUBLISH-AC-01:** Parent lifecycle/status is computed from durable
  assignments and the captured required policy.
- [x] **ORCH-PUBLISH-AC-02:** Payload contains exact repository/commit/trigger,
  definition digest, request authorization provenance, and matrix summaries.
- [x] **ORCH-PUBLISH-AC-03:** Existing runner child IDs are linked to their exact
  assignments and retained across parent updates.
- [x] **ORCH-PUBLISH-AC-04:** Disabled/failed remote publication leaves local
  durable gate truth intact.

## Interfaces and compatibility

- [x] **ORCH-PUBLISH-AC-05:** Parent uses stable external run identity and
  publishes only aggregation/link data, never child artifacts.
- [x] **ORCH-PUBLISH-AC-06:** Tokens, private device coordinates, and detailed
  runner evidence are absent from parent payloads.

## Quality attributes

- [x] **ORCH-PUBLISH-AC-07:** Unit tests cover aggregate statuses, request
  provenance, child links, disabled/errors, and no-artifact behavior.
- [ ] **ORCH-PUBLISH-AC-08:** Current live Mining QA Status displays one parent
  with correct immutable links for every completed child assignment.

## Verification evidence

- `tests.unit.test_orchestrator` verifies gate-only publication and child
  linking, including an assertion that parent must not upload artifacts;
  reconciled 2026-08-10.
- No live parent/child publication was performed for this docs iteration.

## Acceptance rule

Aggregation/payload changes require exhaustive status-policy and privacy tests.
External contract changes require consumer compatibility tests; live display/link
claims require a recorded gate with all children inspected.
