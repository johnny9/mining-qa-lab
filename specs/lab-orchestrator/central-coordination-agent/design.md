# Central coordination agent — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Configuration validator | Enforce explicit mode, central client settings, secret references, and private bindings | `src/mining_qa_lab/config.py` |
| Durable ledger | Persist executions, cursors, claims, snapshots, attempts, cleanup disposition, and outbox | `src/mining_qa_lab/database.py` |
| Agent/worker engine | Heartbeat, pull, claim, renew, bind, execute, and flush completion | `src/mining_qa_lab/engine.py` |
| Assignment boundary | Emit v2 metadata and consume the matching v2 pointer | `src/mining_qa_lab/engine.py` |
| Operator surface | Show central versus local truth and safe pause/recovery controls | `src/mining_qa_lab/web.py` |

## Interfaces and contracts

### CLI

- Existing service commands use the configured mode. `validate` rejects an
  incomplete or ambiguous central configuration without network mutation.
- Pausing new central claims is an authenticated operator action and does not
  stop active cleanup.

### Configuration

Target schema:

```yaml
coordination:
  mode: local
  central:
    base_url: https://status.example
    lab_id: lab-east
    token_env: MINING_QA_LAB_AGENT_TOKEN
    heartbeat_seconds: 30
    poll_seconds: 10
    request_timeout_seconds: 10
    subscriptions:
      gates: [firmware-advisory]
bindings:
  suite_requirements:
    gamma-http-and-stratum:
      setup: gamma-bench
      profile: gamma-read-write
```

`mode` is `local` or `central` and defaults to `local`. Central mode requires
HTTPS except loopback integration, named token environment, positive bounded
timeouts, and at least one subscription/binding for work to be accepted.

### Environment

- `token_env` resolves only at request time. The bearer token and claim token
  never enter YAML, subprocess arguments, general logs, metadata, completion,
  or public records. Private SQLite state may retain only the minimum protected
  capability required for restart-safe renewal/completion.

### Python API

- Typed immutable DTOs mirror the coordination contract.
- Binding resolution accepts a validated portable requirement and frozen Lab
  config, returning one private immutable execution snapshot or a bounded
  decline code.
- Outbox operations are explicit and idempotency-keyed.

### HTTP or external protocols

- Status/Lab behavior follows
  [lab coordination v2](../../../contracts/lab-coordination-v2.md).
- Lab/Testcode behavior follows
  [orchestration v2](../../../contracts/orchestration-v2.md).

### Files, artifacts, payloads, and persistent state

- Add central executions, pull cursor, claim generations, definition/source
  snapshots, private binding snapshots, assignment attempts, and outbox rows.
- An assignment is stable work identity. `assignment_attempts` has immutable
  `attempt_id`, number, state, timing, bounded detail, pointer, child identity,
  archive metadata, and cleanup disposition.
- Raw worker/orchestrator logs and private archives remain local. Only the
  Testcode-produced sanitized child/log links can enter public completion.

## Contract constraints

### Required invariants

- Persist and validate an offer before claim; unique central execution ID is the
  duplicate-work guard.
- Capability advertisement is an eligibility hint, never authorization or
  proof of a safe binding.
- Freeze private binding and source/definition snapshots before local lease or
  runner construction.
- Acquire every local resource before Testcode installation/deployment/run.
- Persist terminal attempt and cleanup disposition before resource release and
  completion enqueue.
- Every v2 pointer correlation field must equal its immutable attempt input.
- Central expiry never cancels Testcode or proves cleanup.

### Forbidden behavior

- Do not serialize internal Lab models and subtract private fields; construct
  registration and published completion from allowlists.
- Do not send device/setup/profile IDs, coordinates, paths, credentials, raw
  logs, exact lease owners, or cleanup internals to Status.
- Do not retry uncertain non-idempotent writes or create a replacement attempt
  solely to repair central state.
- Do not let central mode reinterpret, upload, or delete existing local
  definitions.

## Data and state

Central execution follows `received -> binding -> queued -> running ->
terminal`. Status claim state is separately mirrored with generation and
expiry. Assignment attempts follow `queued -> running -> passed | failed |
error | skipped`. Completion outbox state follows `pending -> delivered |
conflict`, retaining the idempotency key and bounded response code.

## Control and data flow

1. Heartbeat and pull after a durable cursor using bounded client calls.
2. Validate offer/digest/source/deadline, transactionally insert the unique
   central execution plus returned cursor, and decline safely before claim when
   no portable/local policy match exists.
3. Claim, freeze binding, create local run/matrix, and acquire resources.
4. Emit exact v2 metadata, execute Testcode, validate pointer, persist attempt
   and cleanup, then release resources.
5. Build allowlisted completion, enqueue it transactionally, and retry safely
   until delivered or a permanent/late conflict is recorded.

## Failure and recovery

- Invalid offer/binding fails before claim or hardware where possible and uses
  a bounded decline code.
- Restart reopens cursor/execution/claim/outbox; interrupted runner work remains
  fail-closed under existing recovery and never silently resumes.
- Central outage uses bounded exponential backoff and a bounded durable outbox.
- Claim expiry during active work allows cleanup to finish; completion conflict
  remains visible and local evidence stays immutable.

## Compatibility and migration

First normalize existing assignment data into immutable attempt 1 without
changing outcome semantics. Ship v2 readers before writers. Keep central mode
disabled by default and local mode unchanged. Rollback disables the central
loop/writer while preserving additive state and historical evidence.

## Resource and operational constraints

Honor all v2 body/list/lease limits. Cap outbox rows and retained coordination
events by configured count/age, use short SQLite transactions, and keep network,
subprocess, and hardware operations outside write transactions.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Owns explicit mode and private binding validation. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Owns transactions, immutable attempts, local leases, and fail-closed restart. |
| [Assignment execution](../assignment-execution/SPEC.md) | Emits v2 metadata and consumes the v2 pointer. |
| [Parent gate publication](../parent-gate-publication/SPEC.md) | Remains local-mode publication; central mode submits per-Lab completion instead. |
| [Testcode orchestration v2](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/orchestration-v2/SPEC.md) | Owns the runner reader/writer side. |

## Verification approach

Unit-test schema, DTO limits, allowlists, transitions, unique/replay behavior,
SQLite reopen, outbox, expiry, immutable attempts, binding rejection, exact v2
environment/pointer equality, and local-mode compatibility. Then run the
Status-owned full local matrix with two processes and mock devices.
