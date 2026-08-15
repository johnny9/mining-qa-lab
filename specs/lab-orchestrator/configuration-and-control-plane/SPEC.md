# Configuration and control plane

Validate, snapshot, and atomically revise the YAML source of truth while
preventing lost updates and plaintext-secret storage.

- **Lifecycle:** supported
- **Owner:** lab-orchestrator maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** ORCH-CONFIG

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-14: Linked the proposed explicit central mode and private portable
  requirement bindings without changing current schema-v1 behavior.
- 2026-08-10: Linked private external configuration and sandboxed path
  allowances to the service-deployment contract.
- 2026-08-10: Added optional testcode repository/ref policy and required
  per-host managed checkout/venv paths.
- 2026-08-10: Defined schema ownership, cross-reference validation,
  secret-reference policy, optimistic concurrency, backup, and atomic replace.
