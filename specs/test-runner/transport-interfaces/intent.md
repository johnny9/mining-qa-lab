# Transport interfaces — intent

## Problem

Embedded miner APIs and serial links can stall, reset mid-request, emit large
or malformed data, or become unreliable under concurrency. Tests need useful
evidence without turning transport uncertainty into duplicate writes or
unbounded resource use.

## Why it matters

A retried configuration write or oversized device response can change hardware
twice, corrupt state, hang cleanup, exhaust memory, or obscure the actual
failure.

## Stakeholders

- **Adapter author** — needs small transport primitives with explicit failure.
- **Test author** — needs asynchronous observation without transport races.
- **Lab operator** — needs bounded retries, timeouts, and trace evidence.
- **Device** — must not receive concurrent or duplicated writes.

## Desired outcome

Every transport operation has an explicit timeout/size bound, a documented
retry policy, and local evidence. Read-only mode blocks writes before opening a
connection.

## Primary flow

1. Adapter constructs configured interfaces with bounded limits.
2. Safe observations execute asynchronously and publish normalized evidence.
3. Failures are classified, logged without secrets/bodies, and either retried
   only when safe or surfaced to lifecycle recovery.

## Alternate and failure flows

- Transient GET/HEAD failures retry with bounded exponential backoff.
- PATCH/POST/upload failure is not automatically retried.
- Optional WebSocket reconnects; REST remains fallback evidence.
- Serial wildcard paths resolve to exactly one usable device or fail.

## Non-goals

- Making uncertain writes idempotent by assumption.
- Storing HTTP bodies or Stratum passwords in traces.
- Downloading arbitrary recovery tools or DLLs.
