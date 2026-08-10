# ESP-Miner device adapters — acceptance

## Functional behavior

- [x] **TR-BITAXE-AC-01:** Bonanza accepts only board 1002/BZM and Gamma accepts
  only board 602/BM1370.
- [x] **TR-BITAXE-AC-02:** Shared AxeOS behavior provides API, pool, state,
  telemetry, OTA, serial, logs, restart, and cleanup capabilities only when
  configured.
- [x] **TR-BITAXE-AC-03:** Legacy and multi-pool schemas configure and restore
  equivalent values without writing masked credentials or redaction markers.
- [x] **TR-BITAXE-AC-04:** Gamma normalizes portable mining state without
  Bonanza-only lifecycle fields.

## Interfaces and compatibility

- [x] **TR-BITAXE-AC-05:** `bitaxe_602` remains registered and
  `Bitaxe602Device` remains a compatibility alias.
- [x] **TR-BITAXE-AC-06:** Gamma firmware configuration does not require or
  accept a separate bridge lifecycle.

## Quality attributes

- [x] **TR-BITAXE-AC-07:** Optional telemetry outages fall back to REST and
  required telemetry fails explicitly.
- [ ] **TR-BITAXE-AC-08:** Current authorized HIL confirms identity, serial,
  telemetry, mutable restore, and healthy mining for each changed model.

## Verification evidence

- `tests.unit.test_bitaxe_state` — identity, inheritance, WebSocket diffs, and
  normalized state; reconciled 2026-08-10.
- `tests.unit.test_bonanza_lifecycle` — pool and cleanup contracts; reconciled
  2026-08-10.
- Current HIL was not run for this documentation iteration.

## Acceptance rule

Adapter changes are acceptable only with native fixture coverage, exact identity
rejection, capability review, cleanup proof, and an explicit statement of HIL
status.
