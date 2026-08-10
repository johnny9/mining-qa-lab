# Persistence, leases, and recovery — intent

## Problem

Polling, planning, deployment, and hardware runs span process lifetimes. Without
durable transitions and exclusive leases, restarts can lose truth or two jobs
can mutate the same device.

## Why it matters

Ambiguous recovery and concurrent device ownership are safety issues, not only
availability issues.

## Stakeholders

- Lab operators recovering/retrying work.
- Executors that need exclusive setup resources.
- Parent-gate consumers relying on durable status.

## Desired outcome

SQLite is the durable orchestration ledger; state transitions are atomic,
device leases are exclusive, and interrupted work becomes explicit error rather
than being silently resumed.

## Primary flow

Create events/runs/assignments transactionally, atomically claim a queued
assignment and all required resources, persist its terminal result, and release
leases in the same durable operation.

## Alternate and failure flows

- Lease conflict leaves the assignment queued for later work.
- Startup marks interrupted running state as error and clears stale leases.
- Operator cancel/retry creates explicit auditable transitions.

## Non-goals

- Distributed multi-database consensus.
- Transparent mid-test resume after process or host loss.
- Reusing a lease as proof that physical cleanup succeeded.
