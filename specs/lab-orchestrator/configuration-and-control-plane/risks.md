# Configuration and control plane — risks

## Scope

### In

- YAML validation, snapshots, revisions, mutation, backups, and persistence.

### Out

- Secret-vault implementation and runner-profile schema.

## Assumptions

- One service process owns normal writes and the source filesystem supports
  atomic rename.

## Open questions

- When does schema evolution justify a dedicated migration command?

## Failure modes

- A missing cross-reference reaches execution.
- Concurrent edits lose operator intent.
- A write is interrupted after backup but before replacement.
- A secret is hidden under an unrecognized key.

## Security, privacy, and safety

Reject inline secrets recursively and keep configuration/backup permissions
restrictive. Open control-plane access is governed by the operator API spec.

## Performance and resource risks

Whole-document validation/mutation grows with inventory size; keep it bounded
and avoid unbounded request bodies.

## Rollout and rollback

Roll out additive fields with defaults. Restore the backup and previous binary
for incompatible or operationally unsafe changes.
