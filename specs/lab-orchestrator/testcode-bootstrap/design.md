# Testcode bootstrap — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Configuration validator | Validate repository, branch, timeout, and per-host managed paths | `src/mining_qa_lab/config.py` |
| Testcode installer | Resolve, pin, clone/fetch, install, and verify worker testcode | `src/mining_qa_lab/testcode.py` |
| Assignment executor | Run bootstrap before firmware/test and launch its executable | `src/mining_qa_lab/engine.py` |
| External runner provenance guard | Reject expected repository/SHA mismatch before hardware | [`mining-qa-testcode` runner](https://github.com/johnny9/mining-qa-testcode/blob/main/src/miner_testcode/runner.py) |

## Interfaces and contracts

### CLI

- No new operator command. `miner-orchestrator serve` and `run` perform the
  configured bootstrap before assignment execution.
- The resulting executable is `<host.testcode.venv>/bin/miner-test`.

### Configuration

- Root `testcode.enabled` opts in; existing configurations default to disabled.
- `testcode.repository` is a GitHub `owner/repository`; `testcode.ref` is a
  branch; `testcode.install_timeout` bounds each Git, venv, and pip command.
- Every enabled lab host supplies absolute `testcode.checkout` and
  `testcode.venv` paths plus optional `testcode.python` (default `python3`).
- Relative runner profiles resolve inside the installed checkout when enabled.

### Environment

- Bootstrap does not accept credentials in YAML or command arguments. The
  initial implementation clones the configured GitHub repository over HTTPS.
- Normal runner environment remains allowlisted. Expected testcode repository,
  ref, and commit travel inside bounded `MINER_TEST_ORCHESTRATION_METADATA`.

### Python API

- `TestcodeInstaller.ensure(run, host_id, host, config, state_dir)` returns an
  immutable installation record with executable, checkout, exact SHA, public
  metadata, and bounded diagnostic output.
- `HostCommandRunner` applies the same local/SSH command and timeout contract.

### HTTP or external protocols

- `git ls-remote` resolves `refs/heads/<ref>` from the configured GitHub HTTPS
  repository. Git fetch retrieves that immutable SHA into a dedicated remote
  tracking ref. Package dependencies use pip's configured HTTPS behavior.
- SSH commands keep `ForwardAgent=no` and quote each command argument.

### Files, artifacts, payloads, and persistent state

- The managed checkout retains `.git` so runner provenance remains available.
- The dedicated venv contains only runner execution dependencies and scripts;
  it is not the orchestrator service environment.
- `state_dir/testcode/<gate-run>/<host>.json` pins repository, ref, and SHA
  atomically after successful installation. The private worker log includes
  bounded bootstrap progress before runner output.

## Contract constraints

### Required invariants

- “Latest” means the head of the configured branch when the first assignment
  for one gate/host bootstraps; all later assignments for that gate/host use the
  same exact SHA.
- Installation occurs after device lease acquisition but before firmware
  deployment or runner execution; any failure releases the lease.
- Existing checkout origin must name the configured GitHub repository and its
  tracked working tree must be clean. Untracked local profiles may remain.
- Fetch and checkout target an exact 40-character SHA; branch names are never
  passed through a shell locally.
- The installer never modifies the virtual environment importing the active
  orchestrator service.
- Editable installation makes the invoked runner and test files originate from
  the managed checkout, preserving exact source links.
- Runner repository/SHA must equal orchestration metadata before device creation.

### Forbidden behavior

- Do not run `git pull`, execute arbitrary configured install commands, or
  install a moving branch without recording its resolved SHA.
- Do not force-reset or clean a checkout with tracked operator changes.
- Do not reuse the orchestrator service venv as the managed runner venv.
- Do not fall back to an older executable after bootstrap failure.
- Do not let different assignments in one gate/host silently use different
  testcode commits.

## Data and state

Configuration selects the moving branch; the per-gate/host marker converts it
to immutable execution policy. The installation record supplies private worker
paths to the executor and public repository/ref/SHA metadata to the runner.

## Control and data flow

1. Acquire assignment device leases and allocate its worker log.
2. Read an existing gate/host marker or resolve the latest branch SHA.
3. Prepare/verify checkout, exact commit, isolated venv, editable install, and
   imported package path on the local or SSH host.
4. Persist the marker after successful preparation and add expected provenance
   to runner metadata.
5. Deploy firmware if configured, then invoke the installed `miner-test`.
6. Runner independently resolves its checkout and rejects a mismatch before HIL.

## Failure and recovery

- Missing Git/Python/venv/pip, network timeout, wrong origin, dirty tracked
  checkout, unavailable SHA, install failure, or import-path mismatch produces
  assignment `error`, retains bounded worker diagnostics, releases leases, and
  performs no firmware/test action.
- A corrupt/foreign marker fails closed. Deleting the affected marker after
  operator inspection allows a retry to resolve the then-current branch.

## Compatibility and migration

- Bootstrap is additive and disabled by default for existing schema-version-1
  files. Enabling it requires per-host paths and Git/Python tooling.
- The expected metadata fields are additive. Older direct runner invocations
  without them remain valid; incompatible newer runner contracts fail rather
  than falling back silently.

## Resource and operational constraints

- Every resolution/install command has a positive configured timeout; error and
  worker-log output is bounded before persistence.
- One service-level installer lock serializes checkout/venv changes. Disk usage
  includes one managed checkout and venv per configured host.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Assignment execution](../assignment-execution/SPEC.md) | Runs bootstrap and uses the returned executable/profile root. |
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Validates opt-in policy and managed host paths. |
| [Artifacts, privacy, and provenance](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/artifacts-privacy-and-provenance/SPEC.md) | Independently records and verifies the exact executing checkout. |
| [Artifact resolution and deployment](../artifact-resolution-and-deployment/SPEC.md) | Bootstrap must succeed before any firmware deployment. |
| [Service deployment](../service-deployment/SPEC.md) | Owns the separate orchestrator release/venv; worker testcode updates never update or restart that service. |
| [Orchestration contract v1](../../../contracts/orchestration-v1.md) | Carries the exact installed repository/ref/SHA to the runner for independent verification. |

## Verification approach

Unit-test schema defaults/invalid values, latest resolution, marker reuse,
wrong origin, dirty checkout, exact fetch, venv/install/import verification,
local/SSH quoting, executor ordering, failure containment, and runner mismatch.
Live local/SSH installation remains a separate authorized operational check.
