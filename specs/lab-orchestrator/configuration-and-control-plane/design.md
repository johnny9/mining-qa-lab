# Configuration and control plane — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Validator | Normalize schema version 1 and validate references/policies | `src/mining_qa_lab/config.py` |
| Config store | Load, digest, back up, and atomically replace YAML | `src/mining_qa_lab/config.py` |
| REST control plane | Expose snapshots and revision-checked mutations | `src/mining_qa_lab/web.py` |
| Example | Document a complete operator starting point | `src/mining_qa_lab/orchestrator.example.yaml` |

## Interfaces and contracts

### CLI

- `miner-orchestrator validate --config PATH` validates without mutation.
- Service commands receive the YAML path explicitly.

### Configuration

- Root schema version is `1`; primary sections are controller, QA status,
  testcode, repositories, test modules, gates, and lab hosts/devices/setups.
- Optional root testcode policy identifies a safe GitHub branch and timeout;
  enabled policy requires absolute checkout/venv paths on every host.

### Environment

- Secrets use named `*_env` or `*_file` references. Environment lookup happens
  only at the consuming boundary.

### Python API

- `validate_config`, `ConfigSnapshot`, and `ConfigStore` are the canonical
  validation/snapshot/mutation interfaces.

### HTTP or external protocols

- Configuration responses carry an ETag/revision; mutations require a matching
  `If-Match` revision where the API defines concurrency control.

### Files, artifacts, payloads, and persistent state

- Source remains YAML. Replacements use same-filesystem temporary files,
  restrictive permissions, backup of the prior source, and atomic rename.

## Contract constraints

### Required invariants

- IDs, URLs, networks, timeouts, references, deployment targets, and matrices
  are validated before a snapshot becomes active.
- Plaintext values under secret-like keys are rejected.
- Every gate run stores the full validated snapshot and definition digest.
- A stale expected revision never overwrites a newer configuration.

### Forbidden behavior

- Do not persist bearer tokens, passwords, API keys, or private keys inline.
- Do not partially apply a multi-field change.
- Do not mutate configuration captured by an existing gate run.

## Data and state

The active snapshot includes normalized document, source path, revision, and
digest. Backups are recovery artifacts; SQLite gate snapshots are historical
execution truth.

## Control and data flow

1. Read/parse/validate YAML and compute snapshot identity.
2. Serve reads with revision metadata.
3. Validate a proposed whole-document or resource mutation.
4. Check expected revision, back up, atomically replace, and reload.

## Failure and recovery

Validation/concurrency errors leave the current snapshot untouched. An operator
can restore the timestamped backup if an otherwise valid edit is undesirable.

## Compatibility and migration

Breaking schema changes require a new schema version and an explicit migration;
new optional fields should preserve version-1 readers where feasible.

## Resource and operational constraints

Configuration size is bounded by operator policy and loaded as one document;
mutations are serialized by the store lock.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Gate planning and supersession](../gate-planning-and-supersession/SPEC.md) | Consumes validated snapshots and gate definitions. |
| [Lab inventory and preflight](../lab-inventory-and-preflight/SPEC.md) | Owns inventory semantics represented by the schema. |
| [Testcode bootstrap](../testcode-bootstrap/SPEC.md) | Consumes validated repository/ref/timeout policy and per-host managed paths. |
| [Operator API and UI](../operator-api-and-ui/SPEC.md) | Exposes revision-checked control surfaces. |
| [Service deployment](../service-deployment/SPEC.md) | Keeps private YAML outside releases and aligns configured writable paths with the service sandbox. |
| [Configuration and selection](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/configuration-and-selection/SPEC.md) | Runner profiles referenced by modules/setups remain a separate schema. |
| [Central coordination agent](../central-coordination-agent/SPEC.md) | Uses explicit mode, Status client policy, and private requirement bindings as a validated schema extension. |

## Verification approach

Unit-test normalization, testcode path/ref constraints, invalid
cross-references, secret rejection, revision conflicts, backups, atomic
replacement, and API conditional requests.
