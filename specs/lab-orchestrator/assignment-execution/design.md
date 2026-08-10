# Assignment execution — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Assignment executor | Resolve snapshot/resources, deploy, invoke worker, ingest pointer | `src/miner_testcode/orchestrator/engine.py` |
| Database | Select work, acquire/release leases, persist terminal result | `src/miner_testcode/orchestrator/database.py` |
| Firmware deployer | Establish optional gate-wide target firmware first | `src/miner_testcode/orchestrator/firmware.py` |
| Runner | Own test lifecycle, evidence, cleanup, and detailed child publication | `src/miner_testcode/runner.py` |

## Interfaces and contracts

### CLI

- Command is `miner-test --config PROFILE --pattern MODULE_PATTERN`, optionally
  repeated `--device NAME` and `--validation-pr NUMBER` as selected by snapshot.
- Host transport may select a configured runner executable and working directory.

### Configuration

- Hosts define local/SSH transport and worker coordinates; setups define profile,
  devices/runner names, and optional working directory; modules define pattern,
  timeout, profile override, and PR validation behavior.

### Environment

- Start from an explicit controller allowlist, then set:
  `MINER_TEST_ORCHESTRATION_METADATA`, `MINER_TEST_EXTERNAL_RUN_ID`,
  `MINER_TEST_RESULT_POINTER`, `GITHUB_REPOSITORY`, `GITHUB_SHA`,
  `GITHUB_REF_NAME`, and optional `MINER_TEST_PR_NUMBER`.

### Python API

- `AssignmentExecutor.execute(assignment)` consumes a durable assignment and
  records its terminal state rather than returning an in-memory result contract.

### HTTP or external protocols

- SSH execution disables agent forwarding. Remote pointer retrieval is a
  separate bounded command. Deployment and child publication have their own specs.

### Files, artifacts, payloads, and persistent state

- Each assignment gets `state_dir/jobs/<gate>/<assignment>/worker.log` and
  `result-pointer.json`. Logs/details and pointer reads are bounded/validated.

## Contract constraints

### Required invariants

- Execution begins only after atomically acquiring every setup device lease.
- Captured gate configuration and exact commit, not current mutable config,
  define the command and provenance (controller connectivity may use current service config).
- Environment contains only allowlisted values plus explicit runner contract values.
- SSH uses `ForwardAgent=no` and shell quoting for environment/command/cwd.
- Runner owns detailed tests, restoration, and child publication; executor owns
  scheduling, process boundary, pointer ingestion, and durable assignment state.
- Status outside `passed`, `failed`, `error`, `skipped` is normalized to error.

### Forbidden behavior

- Do not execute on a disabled device or without all leases.
- Do not inherit arbitrary service environment or forward SSH agent credentials.
- Do not infer success solely from process exit when a valid pointer says otherwise.
- Do not duplicate hardware cleanup or detailed artifact upload in orchestrator.

## Data and state

Assignment metadata includes gate/assignment/module/platform/setup/attempt,
trigger, gate publication identity, and deployment provenance. Pointer supplies
bounded child status and publisher ID/URL.

## Control and data flow

1. Load immutable run snapshot and acquire device resources.
2. Allocate job paths and ensure optional firmware deployment.
3. Invoke local/SSH runner with explicit command/environment and timeout.
4. Save worker output, ingest pointer, finish assignment, link child if possible.

## Failure and recovery

Any bounded invocation, decode, pointer, or link error is recorded as assignment
error. Runner cleanup is awaited by the process contract; interrupted service
recovery remains fail-closed and requires operator hardware inspection.

## Compatibility and migration

CLI, environment metadata, and pointer schema are cross-component contracts.
Coordinate reader/writer changes and deploy compatible readers before required writers.

## Resource and operational constraints

Only configured host/setup parallelism and exclusive leases permit work.
Process/SSH/pointer waits, logs, and stored error details are bounded.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Supplies exclusive resources and durable outcomes. |
| [Artifact resolution and deployment](../artifact-resolution-and-deployment/SPEC.md) | Runs once before test execution when configured. |
| [Configuration and selection](../../test-runner/configuration-and-selection/SPEC.md) | Runner consumes selected profile/pattern/devices. |
| [Result model and publishing](../../test-runner/result-model-and-publishing/SPEC.md) | Defines child-result pointer and publisher identity. |

## Verification approach

Unit-test exact command/environment, quoting, local/SSH paths, lease conflicts,
deployment failure, timeout, log/pointer handling, status normalization, and links.
