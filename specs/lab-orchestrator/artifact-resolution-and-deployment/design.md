# Artifact resolution and deployment — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Artifact fetcher | Resolve exact workflow/artifact and securely cache firmware | `src/mining_qa_lab/firmware.py` |
| Firmware deployer | Check board/API, perform OTA/reboot verification, write marker | `src/mining_qa_lab/firmware.py` |
| Executor | Invoke deployment once after leases and before runner | `src/mining_qa_lab/engine.py` |
| Config validator | Validate workflow, member, digest, method, and target relationships | `src/mining_qa_lab/config.py` |

## Interfaces and contracts

### CLI

- Deployment is gate policy executed automatically before an assignment; no
  standalone flash command bypasses normal run/lease provenance.

### Configuration

- Repository artifacts define GitHub workflow, artifact name, filename/member,
  optional SHA-256, token reference, waits, and size caps. Gate deployment names
  artifact, target device/role, method, and expected board/version behavior.

### Environment

- GitHub token comes from the configured environment. It is sent only to GitHub
  API/archive endpoints, never to the signed storage redirect target.

### Python API

- `GithubActionsArtifactFetcher.fetch(...)` returns verified local artifact
  provenance; `FirmwareDeployer.ensure(...)` returns sanitized deployment metadata.

### HTTP or external protocols

- GitHub REST resolves workflow/artifact. Device info and OTA use bounded AxeOS
  HTTP endpoints, followed by reboot/readiness verification.

### Files, artifacts, payloads, and persistent state

- Cache paths are content/source scoped with restrictive permissions. A
  per-gate/setup deployment marker is atomically written only after verification.

## Contract constraints

### Required invariants

- Workflow run head SHA exactly equals the gate commit and conclusion is success.
- Archive/firmware bytes and extraction size are bounded; member paths are safe.
- Configured or computed SHA-256 is retained and verified where required.
- Observed device board identity matches deployment policy before OTA.
- Marker identity includes gate/setup/artifact provenance and is written only
  after post-reboot verification.

### Forbidden behavior

- Do not choose the latest build without exact SHA matching.
- Do not follow an artifact redirect while forwarding the GitHub token.
- Do not extract traversal/absolute/symlink-like unsafe members.
- Do not flash an unknown/mismatched board or write success marker before verify.

## Data and state

Artifact provenance records workflow/run/artifact IDs, commit, archive/firmware
digest and size. Deployment state records sanitized identity, never cache secrets.

## Control and data flow

1. Assignment holds all setup device leases.
2. Resolve/download/extract/verify exact artifact.
3. Query target identity and compare board policy.
4. OTA, wait for reboot/identity, write marker, pass provenance to runner metadata.

## Failure and recovery

All preflash failures leave hardware untouched. OTA/reboot failure marks the
assignment error and requires operator inspection; no marker permits silent skip.

## Compatibility and migration

New providers or deployment methods need equivalent exact-source, safe-download,
board, verification, marker, and rollback contracts before support.

## Resource and operational constraints

Waits, response/archive/firmware size, polling, and cache paths are bounded.
Deployment occurs once per gate/setup identity, not once per test module.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Event ingestion and trust](../event-ingestion-and-trust/SPEC.md) | Supplies exact authorized commit. |
| [Lab inventory and preflight](../lab-inventory-and-preflight/SPEC.md) | Supplies target/API and compatibility identity. |
| [Assignment execution](../assignment-execution/SPEC.md) | Acquires leases and invokes deployment before runner. |
| [Firmware lifecycle](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/firmware-lifecycle/SPEC.md) | Runner may validate firmware; orchestrator owns gate-wide predeployment. |

## Verification approach

Unit-test exact-run selection, auth redirect, bounds, malicious archives,
digests, board mismatch, OTA/reboot failures, marker idempotency, and provenance.
