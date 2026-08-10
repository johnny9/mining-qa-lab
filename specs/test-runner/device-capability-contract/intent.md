# Device capability contract — intent

## Problem

Mining devices expose different APIs, lifecycle labels, firmware artifacts, and
telemetry. Embedding model checks in shared tests makes coverage brittle and
prevents new miners from reusing behavior-based tests.

## Why it matters

Capability-based tests can run unchanged on any adapter that truthfully
implements the contract, while unsafe or unsupported operations skip before
hardware use.

## Stakeholders

- **Generic test author** — declares behavior requirements only.
- **Adapter author** — maps native state and operations into portable contracts.
- **Operator** — receives explicit skips rather than accidental partial tests.
- **Publisher consumer** — receives normalized devices and outcomes.

## Desired outcome

Every supported device type has one registered adapter that truthfully
advertises configured capabilities, normalizes state, and implements the full
failure-safe lifecycle.

## Primary flow

1. Configuration names a registered device type.
2. The factory creates its adapter and the test checks required capabilities.
3. The generic test uses `MiningDevice`, `DeviceState`, and `TelemetryCapture`
   without model-specific branches.

## Alternate and failure flows

- Unknown types fail configuration.
- Missing capabilities produce an explicit skip before lifecycle startup.
- Identity mismatch fails before mutation.

## Non-goals

- A universal lowest-common-denominator ASIC driver.
- Advertising capabilities based only on theoretical device support.
- Hiding device-only tests that require a specialized capability.
