# Remote rerun requests — risks

## Scope

### In

- Authenticated rerun intent, exclusive claim, exact validation, local requeue,
  audit, idempotency, and coordinated rollout.

### Out

- Arbitrary test construction, device control from Status, and priority queues.

## Assumptions

- Parent publication has already stored both the public UUID and stable local ID.
- One local orchestrator database remains authoritative for its configured gates.

## Open questions

- Should a later policy add per-user rate limits beyond one active request per
  gate snapshot?

## Failure modes

- Two agents claim one request without an atomic lease.
- Public identity is stale or forged relative to local state.
- Local commit succeeds but Status resolution times out.
- A request resets active work or destroys prior evidence.
- A broadly scoped token claims work for an unintended lab.

## Security, privacy, and safety

Status records intent, not device authority. The lab matches configured public
targets and validates private truth before mutation. Responses and logs use
bounded public identifiers only. Physical execution still requires the normal
lease, preflight, deployment, runner, and cleanup paths.

## Performance and resource risks

Claim one request per normal poll and bound targets, assignment IDs, response
bodies, detail, timeout, and lease duration. One active snapshot request limits
accidental click storms.

## Rollout and rollback

Keep polling disabled by default. Migrate Status, issue the dedicated token,
deploy both versions, verify an empty claim, then enable one lab. Roll back by
disabling polling; never delete unresolved requests or applied local audit rows.
