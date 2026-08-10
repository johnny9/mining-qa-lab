# Persistence, leases, and recovery — risks

## Scope

### In

- SQLite state, transactions, leases, recovery, cancellation, and retry.

### Out

- Distributed scheduling and automatic physical recovery.

## Assumptions

- State storage is local, durable, and writable by one service instance.

## Open questions

- What operational scale would justify explicit migrations or a server database?

## Failure modes

- Host loss after hardware mutation but before terminal persistence.
- Lease leak blocks future work.
- Retried assignment is confused with the prior attempt.
- Filesystem full/corruption prevents a safe transition.

## Security, privacy, and safety

The database may contain local device coordinates and must have restricted host
access. Clearing a lease never asserts that hardware state was restored.

## Performance and resource risks

Long transactions block the service; keep I/O outside them and periodically
manage database/WAL growth under operator policy.

## Rollout and rollback

Back up state before schema changes. Roll back with the compatible binary and
database backup; do not down-convert live state ad hoc.
