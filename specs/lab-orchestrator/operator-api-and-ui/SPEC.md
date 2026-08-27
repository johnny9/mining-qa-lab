# Operator API and UI

Expose network-restricted, authenticated REST and focused local pages for
configuration, gates, trusted triggers, lab inspection, and durable history.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-24
- **Spec ID:** ORCH-API

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-27: Made the Run page list every matching open PR with neutral
  language and added explicit Testcode-module subsets for local/shared runs.
- 2026-08-27: Paginated open PRs at ten per page and condensed each approval
  card while retaining source identity and explicit confirmation.
- 2026-08-27: Added contributor filtering before pagination with matching and
  total result counts.
- 2026-08-27: Added hybrid views for local and shared definitions plus a
  locally authorized same-Lab shared manual-run action.
- 2026-08-24: Added central-agent status/pause/trigger guidance, made blocking
  API work portable across supported Python runtimes, and re-verifies archived
  content before authenticated download.
- 2026-08-10: Added a confirmed overview action for retrying only failed,
  errored, or cancelled gate runs through the authenticated retry API.
- 2026-08-10: Added project/branch-or-commit/device-type manual gate controls
  and authenticated local artifact list, view, and download surfaces.
- 2026-08-10: Linked API health and bounded operational evidence to the
  service-deployment contract.
- 2026-08-10: Defined REST/resource surface, bearer/network policy, optimistic
  mutations, exact trigger actions, lab probes, OpenAPI, pages, and health scope.
