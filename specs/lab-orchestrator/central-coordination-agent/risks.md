# Central coordination agent — risks and scope

## Scope

### In

- Explicit mode, Status client, sanitized capability/subscription, durable
  offers/claims/outbox, private binding, immutable attempts, v2 runner
  correlation, completion, restart, and operator controls.

### Out

- Global definitions/aggregation, detailed runner evidence, device cleanup
  implementation, real enrollment, and migration/deletion of local definitions.

## Assumptions

- Status implements the exact v2 contract and stable idempotent operations.
- SQLite and private state paths remain restricted to the Lab service user.
- A safe local binding can be revalidated independently of advertisement.

## Open questions

- Protected claim-token persistence may later use an OS credential facility;
  the proof of concept can use restricted private state but must never log or
  publish it.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Replayed offer duplicates assignment | Duplicate hardware mutation | unique central execution/reopen tests | Persist before claim and reuse one local identity |
| Binding drift after claim | Wrong target/profile | frozen snapshot comparison | Resolve/freeze before resources and fail closed |
| Claim expires during cleanup | Late/missing global evidence | lease timer and 409 event | finish cleanup, retain evidence, record conflict |
| Retry overwrites prior attempt | Lost audit/evidence | migration/retry assertions | immutable `assignment_attempts` rows |
| Internal model leaks to completion | Lab privacy breach | canary serializer tests | explicit public/private DTOs |

## Security, privacy, and safety

Outbound-only coordination does not broaden hardware authority. Treat agent and
claim tokens as credentials, keep private mappings local, and preserve existing
lease, firmware, runner, and cleanup boundaries.

## Performance and resource risks

Polling, heartbeats, large outboxes, or long attempts can grow load/state. Use
contract caps, bounded backoff, retention limits, short transactions, and one
active execution per local resource.

## Rollout and rollback

Migrate attempts first, deploy dormant readers/state, then enable simulation.
Rollback disables the central loop/writer and retains local mode plus historical
state; never down-convert or delete terminal attempts.
