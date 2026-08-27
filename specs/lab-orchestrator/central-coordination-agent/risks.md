# Central coordination agent — risks and scope

## Scope

### In

- Explicit mode, Status client, sanitized capability/subscription, durable
  offers/claims/outbox, private binding, immutable attempts, v2 runner
  correlation, explicit mock/hardware execution, enrollment, completion,
  restart, and operator controls.

### Out

- Global definitions/aggregation, detailed runner evidence, device cleanup
  implementation, and migration/deletion of local definitions.

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
| Mock behavior reaches a real device binding | Unauthorized reset or false evidence | binding-class command/environment tests | explicit binding type and mutually exclusive fields |
| Hardware process/pointer failure is retried | Duplicate mutation before cleanup is known | launch/failure regression | no automatic hardware retry; require operator inspection |
| Runner output exhausts local storage | Service/host failure during cleanup | bounded-stream regression and state monitoring | drain continuously, retain at most the configured cap, fail explicitly after cleanup |

## Security, privacy, and safety

Outbound-only coordination does not broaden hardware authority. Treat bootstrap,
agent, and claim tokens as credentials, keep private mappings local, and
preserve existing lease, runner, and cleanup boundaries. Hardware bindings must
name the runner devices explicitly and may not inherit arbitrary service state.

## Performance and resource risks

Polling, heartbeats, large outboxes, or long attempts can grow load/state. Use
contract caps, bounded backoff, retention limits, short transactions, and one
active execution per local resource.

## Rollout and rollback

Deploy explicit binding readers, validate mock integration, then enroll and
preflight a paused hardware Lab before its first Status trigger. Rollback pauses
or disables the central loop and retains historical state; never down-convert or
delete terminal attempts. Physical cleanup is independently verified before a
new hardware trigger after an uncertain failure.
