# Gate planning and supersession

Create an idempotent setup-by-module assignment matrix from each eligible event
and supersede stale queued PR work without disturbing running hardware work.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-PLAN

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Allowed authorized manual requests to narrow the configured setup
  matrix by validated device type without altering the captured gate policy.
- 2026-08-10: Defined event eligibility, immutable snapshots/digests, matrix
  construction, required policy, idempotency, and queued-PR supersession.
