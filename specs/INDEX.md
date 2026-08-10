# Specification index

Every feature-level `SPEC.md` appears exactly once. Paths are domain slices,
not source-directory mirrors. Lifecycle values must match the canonical entry.

| Area | Feature | Lifecycle | Link | Summary |
|---|---|---|---|---|
| `test-runner` | Configuration and selection | supported | [SPEC.md](test-runner/configuration-and-selection/SPEC.md) | Resolve runner profiles, devices, tests, environment values, and opt-in validation cases. |
| `test-runner` | Lifecycle and cleanup | supported | [SPEC.md](test-runner/lifecycle-and-cleanup/SPEC.md) | Own a failure-safe device lifecycle with verified mutable-state restoration. |
| `test-runner` | Device capability contract | supported | [SPEC.md](test-runner/device-capability-contract/SPEC.md) | Let generic tests target normalized capabilities instead of miner models. |
| `test-runner` | ESP-Miner device adapters | supported | [SPEC.md](test-runner/esp-miner-device-adapters/SPEC.md) | Adapt Bonanza 1002 and Gamma 602 AxeOS behavior into common contracts. |
| `test-runner` | Transport interfaces | supported | [SPEC.md](test-runner/transport-interfaces/SPEC.md) | Bound and serialize HTTP, WebSocket, serial, and Stratum transport behavior. |
| `test-runner` | Firmware lifecycle | supported | [SPEC.md](test-runner/firmware-lifecycle/SPEC.md) | Apply explicit OTA or USB artifacts and verify target firmware identity. |
| `test-runner` | State, telemetry, and charting | supported | [SPEC.md](test-runner/state-telemetry-and-charting/SPEC.md) | Normalize mining health and retain independently observed telemetry evidence. |
| `test-runner` | Public pool smoke | supported | [SPEC.md](test-runner/public-pool-smoke/SPEC.md) | Verify pool protocol reachability and stable mining with optional device reconfiguration. |
| `test-runner` | Stratum V1 regression | supported | [SPEC.md](test-runner/stratum-v1-regression/SPEC.md) | Exercise deterministic miner-client protocol behavior against a local fake pool. |
| `test-runner` | Artifacts, privacy, and provenance | supported | [SPEC.md](test-runner/artifacts-privacy-and-provenance/SPEC.md) | Preserve useful evidence without leaking identities, secrets, or local coordinates. |
| `test-runner` | Result model and publishing | supported | [SPEC.md](test-runner/result-model-and-publishing/SPEC.md) | Aggregate native unittest outcomes and publish local or remote child results. |
| `lab-orchestrator` | Configuration and control plane | supported | [SPEC.md](lab-orchestrator/configuration-and-control-plane/SPEC.md) | Validate and atomically revise the YAML source of truth with concurrency control. |
| `lab-orchestrator` | Event ingestion and trust | supported | [SPEC.md](lab-orchestrator/event-ingestion-and-trust/SPEC.md) | Turn authorized GitHub, QA feed, schedule, manual, and exact-SHA PR inputs into events. |
| `lab-orchestrator` | Gate planning and supersession | supported | [SPEC.md](lab-orchestrator/gate-planning-and-supersession/SPEC.md) | Build idempotent setup/module assignment matrices and supersede stale queued PR work. |
| `lab-orchestrator` | Persistence, leases, and recovery | supported | [SPEC.md](lab-orchestrator/persistence-leases-and-recovery/SPEC.md) | Persist orchestration state, enforce exclusive devices, and fail closed after interruption. |
| `lab-orchestrator` | Lab inventory and preflight | supported | [SPEC.md](lab-orchestrator/lab-inventory-and-preflight/SPEC.md) | Model hosts, devices, setups, USB identity, probes, photos, and compatibility checks. |
| `lab-orchestrator` | Artifact resolution and deployment | supported | [SPEC.md](lab-orchestrator/artifact-resolution-and-deployment/SPEC.md) | Resolve an exact successful build, verify it, and perform board-checked OTA once. |
| `lab-orchestrator` | Testcode bootstrap | supported | [SPEC.md](lab-orchestrator/testcode-bootstrap/SPEC.md) | Resolve the latest configured testcode branch, pin it per gate and host, and install it safely before each assignment. |
| `lab-orchestrator` | Assignment execution | supported | [SPEC.md](lab-orchestrator/assignment-execution/SPEC.md) | Execute local or SSH runner jobs with bounded environment, logs, timeout, and result pointer. |
| `lab-orchestrator` | Parent gate publication | supported | [SPEC.md](lab-orchestrator/parent-gate-publication/SPEC.md) | Publish aggregate gate state, request provenance, and immutable child-result links. |
| `lab-orchestrator` | Operator API and UI | supported | [SPEC.md](lab-orchestrator/operator-api-and-ui/SPEC.md) | Expose authenticated/network-restricted REST and focused local operator pages. |
| `lab-orchestrator` | Service deployment | supported | [SPEC.md](lab-orchestrator/service-deployment/SPEC.md) | Install, inspect, update, and roll back the orchestrator as an exact-release systemd user service. |
| `project-tooling` | Repository skills | supported | [SPEC.md](project-tooling/repository-skills/SPEC.md) | Package project workflows as portable, validated, safely installable agent skills. |

Allowed lifecycle values: `proposed`, `implementing`, `supported`, `deprecated`,
and `retired`.
