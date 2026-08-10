# Persistence, leases, and recovery — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Database | Schema, transactions, queries, state transitions, and leases | `src/mining_qa_lab/database.py` |
| Engine | Select next work, finish gates, and invoke startup recovery | `src/mining_qa_lab/engine.py` |
| Operator API | Expose history, cancel, and retry controls | `src/mining_qa_lab/web.py` |

## Interfaces and contracts

### CLI

- The service derives the SQLite path from `controller.state_dir`; operators
  use API/CLI actions rather than editing the database.

### Configuration

- `controller.state_dir` locates durable database, jobs, and deployment state.

### Environment

- No database secret is required for local SQLite.

### Python API

- `OrchestratorDatabase` exposes transaction, cursor/event/run/assignment,
  acquire/finish, recovery, supersede, cancel, and retry operations.

### HTTP or external protocols

- Status and mutation endpoints return durable records; an API response is not
  emitted before its database transition commits.

### Files, artifacts, payloads, and persistent state

- SQLite persists source cursors, events, gate runs, assignments, and resource
  leases plus archived artifact path/size/hash/media metadata. Immutable archive
  files live below `state_dir/archive` by assignment and attempt. WAL/foreign-key
  behavior and migrations are initialized on open.

## Contract constraints

### Required invariants

- Run matrix creation is atomic and idempotent.
- Acquiring an assignment and all its resources is one transaction.
- Each `device:<id>` resource has at most one active owner.
- Terminal assignment transition releases its leases.
- Startup recovery never reports interrupted running work as passed or queued.
- Retry is explicit and preserves the prior attempt/history context.
- Artifact rows and archive directories remain attempt-specific; retry never
  overwrites a prior attempt's retained evidence.

### Forbidden behavior

- Do not manually edit SQLite while the service owns it.
- Do not execute before successful lease acquisition.
- Do not silently resume a process-interrupted hardware assignment.
- Do not delete historical terminal results as part of retry.

## Data and state

Events become planned; gate runs move through queued/running/terminal states;
assignments do likewise. Resource leases reference the active assignment.

## Control and data flow

1. Persist event and atomic run matrix.
2. Select queued work and atomically acquire every resource.
3. Execute outside the database transaction.
4. Persist outcome/release leases, then aggregate the gate.

## Failure and recovery

SQLite rollback removes partial transitions. On startup, running assignments and
runs become explicit error states and stale leases are cleared for operator
inspection/retry.

## Compatibility and migration

Schema changes require forward migration and backup/rollback planning. Existing
historical rows retain their original semantic interpretation.

## Resource and operational constraints

SQLite assumes one local service deployment with short transactions. Network
and hardware operations never run while holding a write transaction.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Gate planning and supersession](../gate-planning-and-supersession/SPEC.md) | Creates atomic durable matrices. |
| [Assignment execution](../assignment-execution/SPEC.md) | Requires/releases device leases and stores outcomes. |
| [Parent gate publication](../parent-gate-publication/SPEC.md) | Reads durable aggregate state. |
| [Lifecycle and cleanup](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/lifecycle-and-cleanup/SPEC.md) | Runner cleanup is distinct from orchestrator lease release. |
| [Service deployment](../service-deployment/SPEC.md) | Preserves external SQLite state across exact-release cutover and invokes fail-closed recovery after interruption. |

## Verification approach

Unit-test transaction rollback, duplicate creation, conflicting lease owners,
finish/release, recovery, cancellation, retry, and terminal aggregation.
