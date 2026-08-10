# Stratum V1 regression — acceptance

## Functional behavior

- [x] **TR-STRATUM-AC-01:** The fake server deterministically implements the
  supported subscribe, authorize, work, difficulty, and submit flows.
- [x] **TR-STRATUM-AC-02:** Server lifecycle and all protocol waits are bounded.
- [x] **TR-STRATUM-AC-03:** Scenarios have explicit ordering and later dependent
  scenarios skip after the first prerequisite failure.
- [x] **TR-STRATUM-AC-04:** Device configuration uses normal lifecycle cleanup.

## Interfaces and compatibility

- [x] **TR-STRATUM-AC-05:** Bind address and miner-reachable advertised address
  are distinct configuration concepts.
- [x] **TR-STRATUM-AC-06:** The transcript does not retain authorization
  passwords or unsanitized private identity.

## Quality attributes

- [x] **TR-STRATUM-AC-07:** Loopback unit tests cover supported messages,
  injected responses, timeouts, and shutdown.
- [ ] **TR-STRATUM-AC-08:** A current authorized HIL run proves the target
  firmware reacts correctly and the original pool is restored.

## Verification evidence

- `tests.unit.test_fake_stratum` and `tests.unit.test_stratum` cover local
  protocol behavior; reconciled 2026-08-10.
- Full miner-client HIL was not run for this documentation iteration.

## Acceptance rule

Server-only changes may be accepted with loopback tests. Scenario or device
behavior changes require the affected miner model in HIL plus independent
verification that cleanup restored the original pool.
