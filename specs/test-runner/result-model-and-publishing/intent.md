# Result model and publishing — intent

## Problem

Raw unittest output does not provide a stable machine contract, durable local
report, or reliable link from an orchestrated assignment to its detailed
result.

## Why it matters

Operators need local diagnostics even when networks fail; CI and the lab
orchestrator need a compact authoritative outcome without duplicating runner
evidence or confusing child and parent ownership.

## Stakeholders

- Developers and operators reading detailed test results.
- GitHub and Mining QA Status consumers.
- The lab orchestrator aggregating assignment outcomes.

## Desired outcome

One normalized run summary is rendered locally, optionally published to each
configured backend, and represented to the orchestrator by a small bounded
result pointer.

## Primary flow

Capture native test events, construct the summary, write local JSON/HTML,
publish through configured backends, record publisher outcomes, and atomically
write the external result pointer when requested.

## Alternate and failure flows

- Best-effort publisher failure is recorded without rewriting the test result.
- Required publisher failure makes the runner unsuccessful.
- A direct-upload target is used only after the server supplies an authorized
  upload contract.

## Non-goals

- Publishing the aggregate parent gate.
- Reimplementing lab scheduling or durable gate state.
- Treating remote publication as the only durable local evidence.
