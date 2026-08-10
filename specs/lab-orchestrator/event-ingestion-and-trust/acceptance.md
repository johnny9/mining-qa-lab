# Event ingestion and trust — acceptance

## Functional behavior

- [x] **ORCH-EVENTS-AC-01:** GitHub and QA-feed inputs create idempotent events
  pinned to exact commits and retain durable cursors/ETags.
- [x] **ORCH-EVENTS-AC-02:** Initial branch polling establishes a baseline and
  does not schedule historical head state.
- [x] **ORCH-EVENTS-AC-03:** Branch, base, contributor, trigger, and path policy
  is applied before planning.
- [x] **ORCH-EVENTS-AC-04:** Untrusted PR approval succeeds only when the
  re-fetched full head SHA equals the operator's expected SHA.

## Interfaces and compatibility

- [x] **ORCH-EVENTS-AC-05:** Schedule/manual inputs use the same durable event
  contract and deterministic deduplication.
- [x] **ORCH-EVENTS-AC-06:** Tokens and authorization headers never enter event
  payloads or logs.

## Quality attributes

- [x] **ORCH-EVENTS-AC-07:** Source failures retain the last safe cursor and all
  network operations are bounded.
- [ ] **ORCH-EVENTS-AC-08:** Current live GitHub and QA-feed polling has been
  observed through restart without duplicate or missed eligible events.

## Verification evidence

- `tests.unit.test_orchestrator` and `tests.unit.test_orchestrator_web` cover
  polling, QA cursoring, schedule/path behavior, and exact PR approval;
  reconciled 2026-08-10.
- No live-source restart observation was performed for this docs iteration.

## Acceptance rule

Any trust/cursor/source change requires replay, first-poll, malformed-response,
and exact-identity regressions. Live reliability claims require a recorded poll
and restart against the configured sources.
