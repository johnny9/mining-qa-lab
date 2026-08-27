# Service deployment

Install, update, inspect, and roll back one long-running lab orchestrator as a
hardened systemd user service without losing configuration or durable state.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-24
- **Spec ID:** ORCH-SERVICE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-27: Removed the non-portable `ProtectKernelModules` user-unit
  directive after live activation failed before `ExecStart`; retained
  unprivileged execution and `NoNewPrivileges` as the portable boundary.
- 2026-08-24: Extended idle inspection and update guidance to require a paused
  central agent with zero active private resource leases.
- 2026-08-10: Split first-install and exact-SHA update agent workflows into
  focused skills while retaining the general inspection and recovery skill.
- 2026-08-10: Moved repository and service-release examples to
  `mining-qa-lab` while keeping managed runner paths under
  `mining-qa-testcode`.
- 2026-08-10: Reconciled the supported source workflow and automated evidence;
  live host update and rollback acceptance remains outstanding.
- 2026-08-10: Defined exact-SHA release layout, systemd user-service contract,
  idle update, health verification, and retained-release rollback.
