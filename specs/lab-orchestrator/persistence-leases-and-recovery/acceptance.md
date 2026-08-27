# Persistence, leases, and recovery — acceptance

## Functional behavior

- [x] **ORCH-STATE-AC-01:** Events, runs, matrices, status, pointers, and cursors
  survive database close/reopen.
- [x] **ORCH-STATE-AC-02:** Assignment/resource acquisition is atomic and
  concurrent assignments cannot lease the same device.
- [x] **ORCH-STATE-AC-03:** Terminal assignment transitions release leases and
  retain detail, pointer, and child-result fields.
- [x] **ORCH-STATE-AC-04:** Startup recovery marks interrupted work error and
  clears stale leases instead of silently resuming.

## Interfaces and compatibility

- [x] **ORCH-STATE-AC-05:** Cancel and retry enforce allowed state transitions
  and preserve historical context.
- [x] **ORCH-STATE-AC-06:** Database failures cannot expose a partial gate
  matrix or partial multi-resource lease.

## Quality attributes

- [x] **ORCH-STATE-AC-07:** Unit tests cover exclusive leases, idempotency,
  terminal/recovery transitions, cancel, and retry.
- [ ] **ORCH-STATE-AC-08:** A service-kill recovery drill on the lab host has
  confirmed expected database and physical-device operator workflow.
- [x] **ORCH-STATE-AC-09:** Central retry bounds are enforced per stable
  requirement assignment while attempt ordinals remain unique within the Lab
  execution; restart preserves completed module pointers and does not rerun
  them.

## Verification evidence

- The 86-test Lab unit suite passed on 2026-08-27. Focused central tests prove
  retry limits per stable requirement assignment, globally unique attempt
  ordinals, SQLite reopen, and restart resume that retains the first module's
  pointer while executing only the unfinished module. Status-owned simulation
  `20260827T135058.254730Z` passed replay and Lab restart scenarios with one
  attempt and child per module per Lab.
- `tests.unit.test_orchestrator` covers persistence, leases, recovery, and state
  transitions, including terminal-immutable attempt history across retry and
  reopen; reconciled 2026-08-16.
- No lab-host process-kill drill was performed for this documentation iteration.

## Acceptance rule

Persistence changes require reopen and rollback tests. Lease/recovery changes
require conflict and interrupted-state tests; production recovery claims require
a recorded drill and separate physical cleanup confirmation.
