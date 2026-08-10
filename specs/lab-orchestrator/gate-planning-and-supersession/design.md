# Gate planning and supersession — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Planner | Match events to gates and expand assignments | `src/mining_qa_lab/engine.py` |
| Path matcher | Apply include/exclude change policy | `src/mining_qa_lab/events.py` |
| Database | Atomically create idempotent runs/assignments and supersede queued work | `src/mining_qa_lab/database.py` |
| Config validator | Ensure referenced setup/module matrix is valid | `src/mining_qa_lab/config.py` |

## Interfaces and contracts

### CLI

- Planning is invoked during service poll/tick and after accepted manual or PR
  approval actions; it has no independent mutable CLI contract.

### Configuration

- Gates define repository, triggers, change filters, target setups, test
  modules, required policy (`all` or configured alternative), timeout, schedule,
  and optional deployment.

### Environment

- Planning consumes no secret environment values.

### Python API

- `Planner.plan(config)` returns the count of newly created gate runs.

### HTTP or external protocols

- No direct external protocol; API actions first create durable events.

### Files, artifacts, payloads, and persistent state

- Each run stores event identity, definition digest, full config snapshot,
  required policy, and one assignment per setup/module pair.

## Contract constraints

### Required invariants

- An event/gate definition produces at most one run under the database
  idempotency key.
- Assignment matrix order/content is deterministic from the captured snapshot.
- A manual event with selected device types includes only target setups that
  contain at least one selected type. Empty and unknown selections are rejected;
  omitted selection means every configured target type.
- Platform key is configured or derived consistently from setup device types.
- Supersession affects only eligible stale queued PR runs, never running or
  completed runs.

### Forbidden behavior

- Do not plan from unvalidated live configuration.
- Do not silently add/remove assignments from an existing run.
- Do not mark stale running work superseded without an explicit cancellation
  policy and safe cleanup contract.

## Data and state

Events transition from unplanned to planned. Gate runs and assignments begin
queued with immutable source/policy fields; later status belongs to execution.

## Control and data flow

1. Load unplanned events and validated current configuration.
2. Filter gates and, for manual work, target setups by selected device types.
3. Expand the target matrix.
4. Create run/assignments transactionally using snapshot and digest.
5. Mark event planned and supersede applicable stale queued PR runs.

## Failure and recovery

Transaction failure leaves no partial matrix. An unplanned event is retried;
the unique creation contract makes recovery idempotent.

## Compatibility and migration

Matrix or required-policy semantics are durable historical contracts. Changes
apply to new snapshots/runs and must not reinterpret completed gates.

## Resource and operational constraints

Matrix size is validated/configuration-bounded. Planning performs no network or
hardware I/O.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Event ingestion and trust](../event-ingestion-and-trust/SPEC.md) | Supplies authorized exact-commit events. |
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Supplies validated immutable policy snapshots. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Provides atomic idempotent run creation and supersession. |
| [Assignment execution](../assignment-execution/SPEC.md) | Consumes queued matrix entries. |

## Verification approach

Unit-test every trigger/filter, matrix expansion, digest/snapshot retention,
duplicate planning, required policy, and queued-versus-running supersession.
