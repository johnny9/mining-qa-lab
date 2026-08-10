# Event ingestion and trust

Turn authorized GitHub, QA-feed, schedule, exact-SHA approval, and manual inputs
into idempotent durable source events.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-EVENTS

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Added manual project/source/device-type provenance and automatic
  exact-head resolution from configured `main`, then `master`.
- 2026-08-10: Defined source cursors, first-poll baseline, trusted contributor
  policy, exact PR-head approval, schedule identity, and bounded collection.
