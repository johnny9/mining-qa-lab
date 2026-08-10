# Service deployment

Install, update, inspect, and roll back one long-running lab orchestrator as a
hardened systemd user service without losing configuration or durable state.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-SERVICE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Reconciled the supported source workflow and automated evidence;
  live host update and rollback acceptance remains outstanding.
- 2026-08-10: Defined exact-SHA release layout, systemd user-service contract,
  idle update, health verification, and retained-release rollback.
