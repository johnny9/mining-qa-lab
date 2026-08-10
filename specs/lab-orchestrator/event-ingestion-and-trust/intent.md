# Event ingestion and trust — intent

## Problem

Polling sources can replay history, race branch/PR updates, or allow untrusted
code onto physical hardware unless identity, authorization, and cursor semantics
are explicit.

## Why it matters

A false or stale event can deploy unintended firmware, consume scarce lab time,
or run code that an operator did not approve.

## Stakeholders

- Repository maintainers and untrusted contributors.
- Lab operators approving exact candidate code.
- Planners relying on durable source facts.

## Desired outcome

Every accepted trigger is attributable, deduplicated, policy-authorized, and
pinned to an exact commit before planning.

## Primary flow

Poll the configured source with its cursor/ETag, normalize eligible changes,
apply branch/contributor/path policy, persist an idempotent event, and advance
the cursor transactionally enough to avoid unsafe replay.

## Alternate and failure flows

- First poll establishes a baseline rather than scheduling historical pushes.
- Untrusted PRs require an operator approval tied to the current full head SHA.
- Manual/schedule events use deterministic identities and normal planning.

## Non-goals

- Executing assignments.
- Trusting a PR number without verifying its current head.
- Treating third-party feed ordering as durable local state.
