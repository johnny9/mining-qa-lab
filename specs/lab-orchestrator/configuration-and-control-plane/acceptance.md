# Configuration and control plane — acceptance

## Functional behavior

- [x] **ORCH-CONFIG-AC-01:** Schema version 1 validates all primary sections,
  defaults, identifiers, and cross-references before activation.
- [x] **ORCH-CONFIG-AC-02:** Plaintext secret-like fields are rejected in favor
  of environment/file references.
- [x] **ORCH-CONFIG-AC-03:** Replacements validate first, back up the previous
  source, and atomically install the new YAML.
- [x] **ORCH-CONFIG-AC-04:** Resource mutations preserve unrelated document
  content and reject unknown or invalid references.

## Interfaces and compatibility

- [x] **ORCH-CONFIG-AC-05:** Snapshot responses expose a revision/ETag and
  stale conditional mutations fail without changing disk.
- [x] **ORCH-CONFIG-AC-06:** Gate runs retain their validated configuration
  snapshot and definition digest after later edits.
- [x] **ORCH-CONFIG-AC-09:** Hybrid mode validates the complete central policy
  and local definition graph in one snapshot without merging their identities.

## Quality attributes

- [x] **ORCH-CONFIG-AC-07:** Unit/API tests cover invalid documents, revision
  conflicts, backup, and persistence.
- [ ] **ORCH-CONFIG-AC-08:** A documented restore drill has verified recovery
  from the generated backup on the production service host.

## Verification evidence

- `tests.unit.test_orchestrator` and `tests.unit.test_orchestrator_web` cover
  validation (including opt-in testcode policy), mutation, backup, and
  conditional API behavior; reconciled 2026-08-10.
- No production-host restore drill was run for this documentation iteration.

## Acceptance rule

Schema changes require validator and invalid-input tests plus reconciliation of
every consuming spec. Persistence changes also require an atomicity/rollback
test; production recovery claims require a recorded restore drill.
