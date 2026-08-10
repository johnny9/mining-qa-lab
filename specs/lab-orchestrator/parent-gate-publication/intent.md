# Parent gate publication — intent

## Problem

A gate spans multiple runner children. Consumers need one policy result and
traceable links, but copying child artifacts into the parent creates competing
sources of truth and privacy/schema risk.

## Why it matters

Clear ownership makes the gate auditable: the orchestrator explains why/what
ran and the aggregation decision; each runner explains detailed hardware evidence.

## Stakeholders

- Reviewers and CI systems consuming the aggregate gate.
- Operators diagnosing a matrix assignment.
- Mining QA Status retaining parent/child relationships.

## Desired outcome

One external parent record tracks gate lifecycle and policy, includes exact
request/source provenance and assignment status, and links to independently
published detailed child results.

## Primary flow

Publish queued/running parent identity, update as durable assignments complete,
aggregate final status under required policy, and attach each available child
result ID/link without uploading child evidence.

## Alternate and failure flows

- Publication disabled leaves local durable state authoritative.
- Transient publication error is logged/retried by a later state update without
  falsifying local gate status.
- Assignment without a child link remains visibly unlinked/error as appropriate.

## Non-goals

- Publishing runner artifacts, telemetry, or detailed assertions.
- Recomputing child test truth from worker logs.
- Letting external publication determine local execution success.
