# Testcode bootstrap

Resolve the latest configured testcode branch, pin its exact commit per gate and
host, and install that checkout into an isolated worker environment before each
assignment.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-TESTCODE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Linked the managed worker checkout/venv boundary to the separate
  orchestrator service-deployment lifecycle.
- 2026-08-10: Reconciled supported implementation and automated acceptance;
  live local/SSH operational acceptance remains outstanding.
- 2026-08-10: Defined managed-checkout installation, per-gate latest-branch
  pinning, isolated worker environments, local/SSH behavior, and runner-side
  provenance verification.
