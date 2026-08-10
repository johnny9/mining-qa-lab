# State, telemetry, and charting — intent

## Problem

Firmware families expose different lifecycle and telemetry fields, and an
offline interval is not the same as zero hashrate. Reviewers need concise charts
without losing full local evidence or cluttering them with routine logs.

## Why it matters

Incorrect normalization or lines drawn across outages can produce false mining
health conclusions. Duplicate cumulative charts make class-scoped regressions
harder to interpret.

## Stakeholders

- **Test author** — waits for fresh stable observations and adds meaningful
  milestones.
- **Reviewer** — reads portable state and one chart per device/module.
- **Adapter author** — maps native fields and outages correctly.
- **Publisher** — transports bounded structured series.

## Desired outcome

Tests consume fresh normalized observations, local evidence retains full
bounded streams, offline transitions create gaps, and published output selects
the richest cumulative series per device/module with named result markers.

## Primary flow

1. API polling and optional WebSocket updates produce normalized observations.
2. `DeviceStateStore` wakes waiters only on new generations and telemetry
  records samples or gaps.
3. Test/chart handlers add intentional milestones and automatic named outcomes;
  summaries reduce cumulative snapshots for publication.

## Alternate and failure flows

- WebSocket outage records/falls back without inventing zeros.
- Stable-state timeout reports the latest state.
- Empty or invalid native metric values are omitted rather than coerced to
  misleading data.

## Non-goals

- Long-term telemetry storage inside the runner.
- Treating a pool share as mandatory for every healthy-mining result.
- Using every `INFO` log as a chart marker.
