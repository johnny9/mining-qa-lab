# Central coordination agent

Pull portable advisory work from Status, bind it privately, execute it safely,
and return one correlated per-Lab completion without transferring hardware
authority.

- **Lifecycle:** implementing
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-16
- **Spec ID:** ORCH-CENTRAL

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-16: Implemented explicit central configuration, a bounded v2 client,
  durable cursor/execution/claim/attempt/outbox state, strict offer/pointer
  validation, and the loopback `central-once` execution/recovery path.
- 2026-08-14: Established explicit central mode, portable/private binding,
  durable claim/outbox state, immutable attempts, v2 correlation, and mock-only
  integration behavior.
