# Specification index

Every feature-level `SPEC.md` in this repository appears exactly once. Runner
features are specified in
[`mining-qa-testcode`](https://github.com/johnny9/mining-qa-testcode/tree/main/specs/test-runner).

| Area | Feature | Lifecycle | Link | Summary |
|---|---|---|---|---|
| `lab-orchestrator` | Configuration and control plane | supported | [SPEC.md](lab-orchestrator/configuration-and-control-plane/SPEC.md) | Validate and atomically revise YAML with concurrency control. |
| `lab-orchestrator` | Event ingestion and trust | supported | [SPEC.md](lab-orchestrator/event-ingestion-and-trust/SPEC.md) | Turn authorized feeds, schedules, manual requests, and exact-SHA approvals into events. |
| `lab-orchestrator` | Remote rerun requests | implementing | [SPEC.md](lab-orchestrator/remote-rerun-requests/SPEC.md) | Lease authenticated Status rerun intent and apply it exactly once to matching local work. |
| `lab-orchestrator` | Central coordination agent | implementing | [SPEC.md](lab-orchestrator/central-coordination-agent/SPEC.md) | Pull portable Status work, bind it privately, execute through immutable attempts, and complete it safely. |
| `lab-orchestrator` | Gate planning and supersession | supported | [SPEC.md](lab-orchestrator/gate-planning-and-supersession/SPEC.md) | Build idempotent setup/module matrices and supersede stale queued PR work. |
| `lab-orchestrator` | Persistence, leases, and recovery | supported | [SPEC.md](lab-orchestrator/persistence-leases-and-recovery/SPEC.md) | Persist orchestration state, enforce exclusive devices, and fail closed after interruption. |
| `lab-orchestrator` | Lab inventory and preflight | supported | [SPEC.md](lab-orchestrator/lab-inventory-and-preflight/SPEC.md) | Model hosts, devices, setups, USB identity, probes, photos, and compatibility checks. |
| `lab-orchestrator` | Artifact resolution and deployment | supported | [SPEC.md](lab-orchestrator/artifact-resolution-and-deployment/SPEC.md) | Resolve an exact successful build, verify it, and perform board-checked OTA once. |
| `lab-orchestrator` | Testcode bootstrap | supported | [SPEC.md](lab-orchestrator/testcode-bootstrap/SPEC.md) | Resolve, pin, and safely install the configured testcode before assignments. |
| `lab-orchestrator` | Assignment execution | supported | [SPEC.md](lab-orchestrator/assignment-execution/SPEC.md) | Execute local or SSH runner jobs through the versioned bounded process contract. |
| `lab-orchestrator` | Parent gate publication | supported | [SPEC.md](lab-orchestrator/parent-gate-publication/SPEC.md) | Publish aggregate gate state, request provenance, and immutable child links. |
| `lab-orchestrator` | Operator API and UI | supported | [SPEC.md](lab-orchestrator/operator-api-and-ui/SPEC.md) | Expose authenticated/network-restricted REST and focused operator pages. |
| `lab-orchestrator` | Service deployment | supported | [SPEC.md](lab-orchestrator/service-deployment/SPEC.md) | Install, inspect, update, and roll back an exact-release systemd user service. |
| `project-tooling` | Repository skills | supported | [SPEC.md](project-tooling/repository-skills/SPEC.md) | Package workflows as portable, validated, safely installable agent skills. |

Allowed lifecycle values: `proposed`, `implementing`, `supported`, `deprecated`,
and `retired`.
