# Remote rerun requests

Accept authenticated rerun intent from Mining QA Status through a leased queue,
then validate and apply it idempotently against private lab state.

- **Lifecycle:** implementing
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-RERUN

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Defined the authenticated Status request, exclusive lab claim,
  exact parent/run validation, selected-assignment rerun, and rollout boundary.
