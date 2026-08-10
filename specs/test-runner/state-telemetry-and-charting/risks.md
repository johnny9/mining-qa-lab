# State, telemetry, and charting — risks and scope

## Scope

### In

- Normalized mining state, async wait semantics, telemetry samples/gaps,
  markers, downsampling, and module-level reduction.

### Out

- Long-term monitoring, alerting, pool accounting, and chart rendering owned by
  Mining QA Status beyond payload compatibility.

## Assumptions

- Native values are sampled often enough to support stable-window criteria.
- Positive hashrate plus fresh work and no faults is a useful portable mining
  signal without requiring a share in every short window.

## Open questions

- Additional miner families may need capability-specific metrics beyond the
  standard four without bloating generic charts.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Offline rendered as zero | False performance drop | Gap unit tests | Explicit gap events |
| Stale state satisfies wait | False stability | Generation tests | Require new observations |
| Wrong unit | Misleading comparison | Metric fixture tests | Canonical unit contract |
| Duplicate cumulative charts | Review noise | Publisher reduction tests | Richest series per module |
| Unbounded samples | Memory/payload growth | Limit tests/config | Bound and downsample |

## Security, privacy, and safety

- Raw state may contain private native fields. Publication sanitation and
  stable public device labels remain mandatory.

## Performance and resource risks

- Higher sampling improves fidelity but can overload embedded APIs or expand
  artifacts. Cadence and bounds must be considered together.

## Rollout and rollback

- Add metrics and semantics with fixture and renderer compatibility first.
  Revert normalization changes if they invalidate known native examples.
