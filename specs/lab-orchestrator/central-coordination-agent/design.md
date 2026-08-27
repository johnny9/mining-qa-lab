# Central coordination agent — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Configuration validator | Enforce explicit mode, central client settings, secret references, and private bindings | `src/mining_qa_lab/config.py` |
| Durable ledger | Persist executions, cursors, claims, snapshots, attempts, cleanup disposition, and outbox | `src/mining_qa_lab/database.py` |
| Agent/worker engine | Heartbeat, pull, claim, renew, bind, execute, and flush completion | `src/mining_qa_lab/central.py` |
| Assignment boundary | Emit v2 metadata and consume the matching v2 pointer | `src/mining_qa_lab/central.py` |
| Operator surface | Show central versus local truth and safe pause/recovery controls | `src/mining_qa_lab/web.py` and `src/mining_qa_lab/cli.py` |

## Interfaces and contracts

### CLI

- `central-once` processes one bounded page in central mode. `central-agent`
  runs the persistent heartbeat/pull/claim/outbox loop and supports a bounded
  `--max-cycles` diagnostic mode. `validate` rejects an incomplete or ambiguous
  central configuration without network mutation.
- Pausing new central claims is an authenticated operator action and does not
  stop active cleanup.
- `central-register --public-label LABEL --agent-environment-file PATH` binds
  the app-issued token named by central `token_env` and creates a new private
  environment file containing that same token. It never prints the token and
  refuses to overwrite an existing file.

### Configuration

Central production binding schema:

```yaml
coordination:
  mode: central
  central:
    base_url: https://status.example
    lab_id: lab-east
    token_env: MINING_QA_TOKEN
    heartbeat_seconds: 30
    poll_seconds: 10
    request_timeout_seconds: 10
    retry_backoff_seconds: 2
    max_retry_backoff_seconds: 60
    max_attempts: 3
    subscriptions:
      gates: [firmware-advisory]
bindings:
  suite_requirements:
    gamma-http-and-stratum:
      execution: hardware
      profile: /private/profiles/gamma-read-write.toml
      testcode_root: /private/checkouts/mining-qa-testcode
      testcode_commit: 0123456789abcdef0123456789abcdef01234567
      runner_executable: /private/venvs/mining-qa-testcode/bin/miner-test
      runner_devices: [gamma-02]
      timeout_seconds: 3600
      platform_class: gamma
      device_model: gamma-602
      capabilities: [http, stratum-v1]
      resources: [device:gamma-02]
```

`mode` is `local` or `central` and defaults to `local`. Central mode requires
HTTPS except loopback integration, named token environment, positive bounded
timeouts, and at least one subscription/binding for work to be accepted. Every
binding requires `execution: mock | hardware`. A mock binding replaces the
hardware-only executable/devices with `mock_base_url_env` and is accepted only
when that environment and the central Status service both resolve to loopback.
Hardware bindings never receive mock reset behavior or integration-only
environment variables.

### Environment

- `token_env` resolves only at request time. The bearer token and claim token
  never enter YAML, subprocess arguments, general logs, metadata, completion,
  or public records. Private SQLite state may retain only the minimum protected
  capability required for restart-safe renewal/completion.
- The app-issued Lab token combines central coordination, result publication,
  and artifact upload. The Lab maps it to `MINING_QA_TOKEN` for its trusted
  exact-SHA runner without exposing the service-side environment-variable name;
  unrelated service credentials remain filtered.

### Python API

- Typed immutable DTOs mirror the coordination contract.
- Binding resolution accepts all validated portable requirements and frozen
  Lab config, returning an ordered immutable requirement-to-binding plan or a
  bounded decline code. Every requirement must match exactly one binding.
- Outbox operations are explicit and idempotency-keyed.

### HTTP or external protocols

- Status/Lab behavior follows
  [lab coordination v2](../../../contracts/lab-coordination-v2.md).
- Lab/Testcode behavior follows
  [orchestration v2](../../../contracts/orchestration-v2.md).

### Files, artifacts, payloads, and persistent state

- `central_executions`, `central_attempts`, `central_resource_leases`,
  `central_agent_control`, and `central_outbox` plus the shared source cursor
  persist executions, pull position, claim generations, definition/source
  snapshots, private binding-plan snapshots, per-requirement assignment
  attempts, resource owners,
  pause/backoff state, and outbox rows.
- An assignment is stable work identity. `central_attempts` has immutable
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
- Freeze the complete ordered private binding plan and source/definition
  snapshots before local lease or runner construction.
- Acquire every local resource before Testcode installation/deployment/run.
- Revalidate every plan item's exact clean Testcode checkout, executable,
  profile, and private device selectors after lease acquisition and before its
  runner launch.
- If the portable suite carries Testcode catalog provenance, require its
  repository and commit to match every private binding. Pass a bounded
  `MINER_TEST_MODULE_OPTIONS` selection only for the matching module; Testcode
  revalidates it before constructing devices.
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
- Do not automatically retry a hardware binding after process launch or infer
  physical cleanup from process exit, lease release, or a central claim state.

## Data and state

Central execution follows `received -> binding -> queued -> running ->
terminal`. Status claim state is separately mirrored with generation and
expiry. Each selected requirement has one stable assignment and immutable
attempts following `queued -> running -> passed | failed | error | skipped`.
Completion outbox state follows `pending -> delivered | conflict`, retaining
the idempotency key and bounded response code.

## Control and data flow

1. Heartbeat and pull after a durable cursor using bounded client calls.
2. Validate offer/digest/source/deadline, transactionally insert the unique
   central execution plus returned cursor, and decline safely before claim when
   no portable/local policy match exists.
3. Claim, freeze the ordered binding plan, create stable per-requirement
   assignments, and atomically acquire the union of all private resources.
4. In suite order, emit exact v2 metadata and that requirement's portable
   pattern with its private device selectors, execute Testcode through the
   selected binding class, validate the pointer, and persist the immutable
   attempt plus cleanup disposition. Restart skips only requirements with a
   publishable terminal pointer.
5. Aggregate the module statuses, build one allowlisted completion with one
   child per selected requirement, enqueue it transactionally, release the
   resource union only after terminal persistence, and retry delivery safely
   until delivered or a permanent/late conflict is recorded.

## Failure and recovery

- Invalid offer/binding fails before claim or hardware where possible and uses
  a bounded decline code.
- Restart reopens cursor/execution/claim/outbox; interrupted runner work remains
  fail-closed under existing recovery and never silently resumes.
- Missing/malformed pointer or process failure after a hardware launch produces
  one terminal local attempt and a sanitized error completion when the claim is
  still usable. No later module launches after an uncertain hardware failure.
  Automatic retries remain available only to deterministic mock integration
  bindings and are counted per stable requirement assignment.
- Central outage uses bounded exponential backoff and a bounded durable outbox.
- Claim expiry during active work allows cleanup to finish; completion conflict
  remains visible and local evidence stays immutable.

## Compatibility and migration

Ship the app-issued-token registration reader before using the new Admin token.
Existing proof-of-concept bindings declare `execution: mock`; ambiguity fails
validation. Local mode remains unchanged. Rollback pauses/disables the central
loop while preserving additive state and historical evidence.

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
SQLite reopen, outbox, expiry, immutable per-requirement attempts, complete-plan
binding rejection, multi-module ordering/recovery/completion, mock/real command
and environment separation, output bounds, terminal hardware failure, exact v2
environment/pointer equality, and local-mode compatibility. Then run the
Status-owned full local matrix with two processes and mock devices. A real Lab
requires a separate authorized preflight/HIL and cleanup observation.
