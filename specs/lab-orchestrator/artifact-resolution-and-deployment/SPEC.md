# Artifact resolution and deployment

Resolve a successful build for the exact gate commit, verify its archive and
firmware identity, and perform board-checked OTA at most once per setup/run.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-DEPLOY

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Defined exact-SHA workflow resolution, bounded secure extraction,
  digest/cache provenance, board precheck, OTA verification, and deployment marker.
