# Lab inventory and preflight — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Inventory validator | Validate host/device/setup relationships and coordinates | `src/miner_testcode/orchestrator/config.py` |
| Probe API | Perform bounded host, device, USB, photo, and setup checks | `src/miner_testcode/orchestrator/web.py` |
| Operator UI | Present logical identity and preflight outcomes | `src/miner_testcode/orchestrator/ui.py` |
| Executor/deployer | Consume setup resources after leases | `src/miner_testcode/orchestrator/engine.py`, `src/miner_testcode/orchestrator/firmware.py` |

## Interfaces and contracts

### CLI

- Inventory is configured in YAML; operational probes are exposed by REST/UI.

### Configuration

- Hosts define local/SSH transport and work coordinates; devices define stable
  name/type/host, private addresses, USB identity, tags, enablement, and
  optional photo data; setups map roles to devices and a runner profile.

### Environment

- SSH/process environment follows the execution allowlist; inventory contains
  references, not credentials.

### Python API

- Validated inventory is a normalized mapping consumed from `ConfigSnapshot`.

### HTTP or external protocols

- `/api/v1/lab/hosts/{id}/probe`, device probes/photos, and setup preflight
  return bounded structured status through the authenticated API.

### Files, artifacts, payloads, and persistent state

- Preflight is current observational data, not a durable gate result. Photos are
  size/type bounded and are not child-test evidence by default.

## Contract constraints

### Required invariants

- Every setup device/host/profile reference validates before activation.
- Public/operator labels are stable logical IDs; private API/serial coordinates
  remain control-plane data.
- Preflight performs read-only checks and reports each required dependency.
- USB identity and firmware board compatibility are checked before destructive
  deployment paths where configured.

### Forbidden behavior

- Do not mutate/reboot/flash a device during preflight.
- Do not expose private coordinates in remotely published gate payloads.
- Do not equate API reachability with runner capability or mining health.
- Do not let a photo endpoint return unbounded/arbitrary filesystem data.

## Data and state

Logical inventory is durable YAML; current probe results are ephemeral response
data. Assignment snapshots retain the inventory used for that run.

## Control and data flow

1. Resolve setup and referenced host/devices.
2. Perform bounded transport/API/USB checks.
3. Compare declared and observed identity/capability where available.
4. Return a per-check report; execution independently acquires leases later.

## Failure and recovery

Probe timeout/failure is explicit and does not alter inventory/device state.
Operators repair configuration or hardware and rerun preflight.

## Compatibility and migration

New device coordinates/capability declarations are additive schema fields until
required. Role changes must stay compatible with referenced runner profiles.

## Resource and operational constraints

Every subprocess/network/photo operation has timeout and output/size bounds.
Probes should be safe to repeat and must not monopolize shared hardware.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Validates and persists inventory. |
| [Artifact resolution and deployment](../artifact-resolution-and-deployment/SPEC.md) | Uses board/API identity before OTA. |
| [Assignment execution](../assignment-execution/SPEC.md) | Resolves host/profile/devices and leases setup resources. |
| [Device capability contract](../../test-runner/device-capability-contract/SPEC.md) | Runner validates runtime test capabilities after launch. |

## Verification approach

Unit/API-test invalid references, disabled devices, local/SSH probe command
construction, API timeouts, USB mismatch, preflight aggregation, and photo caps.
