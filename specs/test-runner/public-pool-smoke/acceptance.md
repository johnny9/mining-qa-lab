# Public pool smoke — acceptance

## Functional behavior

- [x] **TR-POOL-SMOKE-AC-01:** The independent probe completes subscribe,
  authorize, and configured job reception within a timeout.
- [x] **TR-POOL-SMOKE-AC-02:** Observational mode verifies existing host/port
  and performs no device write.
- [x] **TR-POOL-SMOKE-AC-03:** Reconfiguration mode uses adapter cleanup and
  refuses unsafe write-only password mutation.
- [x] **TR-POOL-SMOKE-AC-04:** Share acceptance is recorded when available but
  is optional by default.

## Interfaces and compatibility

- [x] **TR-POOL-SMOKE-AC-05:** Pool/probe identities and passwords remain
  redacted from published evidence.
- [x] **TR-POOL-SMOKE-AC-06:** Stable-window criteria use normalized portable
  state rather than a model-specific lifecycle label.

## Quality attributes

- [x] **TR-POOL-SMOKE-AC-07:** Probe, readiness, work age, sample count, and
  cleanup are bounded.
- [ ] **TR-POOL-SMOKE-AC-08:** A current authorized end-to-end run proves live
  public job reception, stable healthy device mining, and original pool restore.

## Verification evidence

- `tests.unit.test_stratum` — independent probe handshake/job protocol;
  reconciled 2026-08-10.
- Source and lifecycle unit tests cover configuration and cleanup paths.
- Full public-pool HIL was not run for this documentation iteration.

## Acceptance rule

Protocol-only work may be accepted with loopback tests, but changes to device
reconfiguration or live health criteria require explicit target HIL and verified
post-test restoration before claiming end-to-end acceptance.
