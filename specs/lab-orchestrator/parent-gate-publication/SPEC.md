# Parent gate publication

Publish aggregate gate state, request provenance, assignment summaries, and
immutable child-result links without duplicating detailed test artifacts.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-PUBLISH

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-14: Clarified that proposed central mode submits per-Lab completion
  while existing local mode retains parent-gate publication.
- 2026-08-10: Made both the public parent UUID and stable local external ID
  required rerun-correlation inputs.
- 2026-08-10: Clarified that the private lab archive is additive redundancy and
  never replaces detailed child publication or parent/link publication.
- 2026-08-10: Defined parent ownership, aggregate status policy, request
  provenance, child linking, idempotent external identity, and failure semantics.
