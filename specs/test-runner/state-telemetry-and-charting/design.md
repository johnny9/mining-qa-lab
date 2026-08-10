# State, telemetry, and charting — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Normalized state | Portable status fields and event serialization | `src/miner_testcode/state.py:DeviceState` |
| State store | Generation-based async waiting and timeout context | `src/miner_testcode/state.py:DeviceStateStore` |
| Telemetry capture | Normalize metrics, samples, gaps, markers, downsample | `src/miner_testcode/telemetry.py` |
| Adapter mapping | Derive state/metrics from native AxeOS data | `src/miner_testcode/devices/bitaxe.py` |
| Result reduction | Select richest series per device/module | `src/miner_testcode/results.py:RunSummary.telemetry_series` |

## Interfaces and contracts

### CLI

- No dedicated flags; sampling cadence and limits are profile settings.

### Configuration

- API poll interval and WebSocket reconnect/ping/message/sample limits.
- Tests configure stable sample count, readiness timeout, minimum hashrate, and
  maximum work age.

### Environment

- None.

### Python API

- `DeviceState`, `DeviceStateStore.wait_for`, `TelemetryCapture`,
  `ChartMarkerHandler`, `log_chart`, and `MinerTestCase.chart`.

### HTTP or external protocols

- Consumes AxeOS REST/WebSocket native data. Published series is embedded in
  local JSON/HTML and Mining QA result payloads.

### Files, artifacts, payloads, and persistent state

- `device-state.jsonl` contains normalized observation events.
- `telemetry.jsonl` contains the full run stream and gaps.
- Structured result telemetry retains at most the configured publication
  maximum (currently 2,000 evenly spaced samples with endpoints).

## Contract constraints

### Required invariants

- `mining_active` requires positive hashrate and rejects pause, fault,
  overheat/system fault, and blocking native lifecycle.
- Waits require new matching generations; stale state cannot satisfy a new
  sample count.
- Offline transitions are gaps without metric values.
- Routine lifecycle progress stays `INFO`; chart markers are intentional suite
  or test milestones and named outcomes.
- Cumulative class-scoped snapshots publish once per device/module using the
  richest duration/sample/marker score.

### Forbidden behavior

- Do not convert absence/offline to zero.
- Do not connect published lines across explicit gaps.
- Do not publish every cumulative test snapshot as a duplicate chart.
- Do not include private marker text without redaction.

## Data and state

- The latest `DeviceState` plus generation lives in an async condition store.
- Telemetry samples and markers are bounded in memory; complete bounded JSONL
  remains local until publication selection.

## Control and data flow

1. Adapter normalizes a native API/WebSocket observation.
2. State store updates and telemetry records sample/gap.
3. Tests wait for consecutive fresh predicate matches and add markers.
4. Result summary chooses one series per device/module and publishers render it.

## Failure and recovery

- Observation timeout → error includes latest state.
- Consecutive offline observations → one continuous gap rather than duplicate
  zero samples.
- WebSocket failure → API fallback source until reconnection.

## Compatibility and migration

- New metrics are additive and need unit normalization plus publisher support.
  Changing units or `mining_active` semantics is compatibility-sensitive.

## Resource and operational constraints

- Default REST cadence is 0.5 seconds; sample/message counts are bounded.
  Downsampling preserves first and last points.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Supplies native normalization and sources. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Supplies REST/WebSocket observations and outage signals. |
| [Public pool smoke](../public-pool-smoke/SPEC.md) | Uses stable mining/work predicates. |
| [Result model and publishing](../result-model-and-publishing/SPEC.md) | Carries and renders the reduced series. |
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Sanitizes marker and raw state evidence. |

## Verification approach

- Unit-test normalization, new-generation waits, timeouts, gaps, markers,
  downsampling endpoints, and module-level reduction.
