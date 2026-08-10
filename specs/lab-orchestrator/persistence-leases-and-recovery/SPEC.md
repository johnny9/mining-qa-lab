# Persistence, leases, and recovery

Persist orchestration truth, serialize shared-device ownership, and recover
interrupted work into explicit fail-closed states.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-STATE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Persisted archived artifact metadata per assignment attempt while
  keeping immutable attempt files outside SQLite.
- 2026-08-10: Linked external durable state, graceful restart, and fail-closed
  interruption handling to the service-deployment contract.
- 2026-08-10: Defined SQLite transaction boundaries, event/run/assignment state,
  exclusive resource leases, cancellation/retry, and restart recovery.
