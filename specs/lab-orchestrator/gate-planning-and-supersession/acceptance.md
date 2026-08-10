# Gate planning and supersession — acceptance

## Functional behavior

- [x] **ORCH-PLAN-AC-01:** Eligible events expand into exactly the configured
  setup-by-module assignments with deterministic platform keys.
- [x] **ORCH-PLAN-AC-02:** Replanning the same event/gate creates no duplicate
  run or assignments.
- [x] **ORCH-PLAN-AC-03:** Each run retains the validated configuration snapshot,
  gate definition digest, and required policy used to create it.
- [x] **ORCH-PLAN-AC-04:** New PR heads supersede applicable stale queued work
  without rewriting running/completed work.

## Interfaces and compatibility

- [x] **ORCH-PLAN-AC-05:** Requested-gate, trigger enablement, repository, and
  changed-path policy all constrain eligibility.
- [x] **ORCH-PLAN-AC-06:** A partial matrix is never externally visible after a
  failed creation transaction.
- [x] **ORCH-PLAN-AC-09:** Manual device-type selections deterministically
  narrow setup assignments; omitted selection means all target types and empty
  or unknown selections fail before planning.

## Quality attributes

- [x] **ORCH-PLAN-AC-07:** Unit tests cover idempotency, filters, snapshotting,
  matrix formation, and supersession status boundaries.
- [ ] **ORCH-PLAN-AC-08:** A current service run has demonstrated expected
  supersession under concurrent polling and operator inspection.

## Verification evidence

- `tests.unit.test_orchestrator` covers planning, path matching, snapshotting,
  and database status behavior; reconciled 2026-08-10.
- No live concurrent-poll supersession demonstration was run for this iteration.

## Acceptance rule

Planning changes require deterministic matrix and idempotency tests, including
old/new config snapshots. Supersession changes also require explicit tests for
queued, running, and terminal states.
