# Central coordination agent

Pull portable advisory work from Status, bind it privately, execute it safely,
and return one correlated per-Lab completion without transferring hardware
authority.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-27
- **Spec ID:** ORCH-CENTRAL

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-27: Unified central coordination and trusted-runner publication on
  one app-issued, Lab-bound token and removed bootstrap-only enrollment.
- 2026-08-24: Completed the production-binding expansion: explicit mock versus
  hardware execution, private runner/device selection, bounded allowlisted
  process execution, fail-closed hardware retry policy, enrollment tooling,
  long-running service verification, and nine-scenario system validation.
- 2026-08-16: Implemented explicit central configuration, a bounded v2 client,
  durable cursor/execution/claim/attempt/outbox state, strict offer/pointer
  validation, and the loopback `central-once` execution/recovery path.
- 2026-08-16: Added immutable retry attempts, exact private binding/source
  preflight, central resource leases, continuous bounded agent/backoff state,
  authenticated pause/resume/status controls, and full two-Lab simulation
  evidence.
- 2026-08-14: Established explicit central mode, portable/private binding,
  durable claim/outbox state, immutable attempts, v2 correlation, and mock-only
  integration behavior.
