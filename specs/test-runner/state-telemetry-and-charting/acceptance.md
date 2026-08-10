# State, telemetry, and charting — acceptance

## Functional behavior

- [x] **TR-TELEMETRY-AC-01:** Portable state rejects false active-mining cases
  for zero hashrate, pause, fault, overheat, maintenance, or safe-off lifecycle.
- [x] **TR-TELEMETRY-AC-02:** Stable waits consume new generations and timeout
  with the latest observed state.
- [x] **TR-TELEMETRY-AC-03:** Consecutive offline observations produce an
  explicit gap without invented metric zeros.
- [x] **TR-TELEMETRY-AC-04:** Markers preserve suite/test meaning and automatic
  result markers include the test method name.

## Interfaces and compatibility

- [x] **TR-TELEMETRY-AC-05:** Standard metrics retain documented units: GH/s,
  degrees Celsius, MHz, and RPM.
- [x] **TR-TELEMETRY-AC-06:** Published series chooses one richest cumulative
  snapshot per device/module and downsampling preserves endpoints.

## Quality attributes

- [x] **TR-TELEMETRY-AC-07:** Samples, messages, and published points are
  bounded while full bounded local JSONL evidence remains available.

## Verification evidence

- `tests.unit.test_bitaxe_state` — mining-state and native telemetry
  normalization; reconciled 2026-08-10.
- `tests.unit.test_state` — fresh generation and timeout behavior; reconciled
  2026-08-10.
- `tests.unit.test_telemetry` and publisher telemetry tests — gaps, markers,
  downsampling, and one-chart reduction; reconciled 2026-08-10.

## Acceptance rule

Telemetry changes are acceptable only with explicit units, positive and
negative state fixtures, fresh-observation semantics, gap behavior, bounded
resource proof, privacy-safe markers, and publisher compatibility tests.
