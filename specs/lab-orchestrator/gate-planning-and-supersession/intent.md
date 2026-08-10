# Gate planning and supersession — intent

## Problem

One source event may map to multiple gates, setups, and test modules. Retries or
new PR heads must not create duplicate matrices or spend lab time on stale
queued candidates.

## Why it matters

Planning is where repository intent becomes physical work. The mapping must be
deterministic, explainable, and frozen against later configuration changes.

## Stakeholders

- Repository maintainers defining gate policy.
- Lab operators allocating setup capacity.
- Parent-gate consumers interpreting required results.

## Desired outcome

Each eligible event/gate pair yields at most one immutable gate run with the
expected setup/module assignments and required-result policy.

## Primary flow

Read unplanned events, match repository/trigger/path/requested gate, expand the
configured target matrix, persist the run with snapshot/digest, and mark the
event planned.

## Alternate and failure flows

- Ineligible events are marked considered without creating work.
- Replanning is idempotent.
- A newer approved head supersedes only stale queued runs for that PR/gate.

## Non-goals

- Acquiring device leases or executing assignments.
- Mutating a planned run when configuration changes.
- Cancelling already-running hardware merely because a newer head exists.
