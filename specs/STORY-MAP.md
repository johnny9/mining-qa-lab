# Story map

This map navigates by operator outcome. [INDEX.md](INDEX.md) is the complete
feature directory.

## Admit only authorized work

- Maintain one validated revisioned lab configuration →
  [Configuration and control plane](lab-orchestrator/configuration-and-control-plane/SPEC.md)
- Convert trusted events and exact-SHA approvals without broadening authority →
  [Event ingestion and trust](lab-orchestrator/event-ingestion-and-trust/SPEC.md)
- Expand a gate deterministically and retire stale queued PR heads →
  [Gate planning and supersession](lab-orchestrator/gate-planning-and-supersession/SPEC.md)

## Protect shared lab resources

- Keep device use exclusive and recoverable across service restarts →
  [Persistence, leases, and recovery](lab-orchestrator/persistence-leases-and-recovery/SPEC.md)
- Inspect hosts, USB identity, devices, setups, and preflight failures →
  [Lab inventory and preflight](lab-orchestrator/lab-inventory-and-preflight/SPEC.md)
- Deploy the exact successful firmware artifact to the expected board →
  [Artifact resolution and deployment](lab-orchestrator/artifact-resolution-and-deployment/SPEC.md)

## Execute the external test suite

- Pin and install the latest approved testcode branch without moving during a
  gate → [Testcode bootstrap](lab-orchestrator/testcode-bootstrap/SPEC.md)
- Run the selected module locally or over SSH and consume its bounded pointer →
  [Assignment execution](lab-orchestrator/assignment-execution/SPEC.md)
- Archive and inspect hash-verified child logs locally while retaining remote
  publication → [Assignment execution](lab-orchestrator/assignment-execution/SPEC.md)
- Publish one aggregate gate linked to external detailed child evidence →
  [Parent gate publication](lab-orchestrator/parent-gate-publication/SPEC.md)

Detailed tests, device adapters, cleanup, and child publication are outcomes of
the separate
[`mining-qa-testcode` story map](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/STORY-MAP.md).

## Operate and deploy the service

- Use REST or focused pages without exposing an unsafe mutation surface →
  [Operator API and UI](lab-orchestrator/operator-api-and-ui/SPEC.md)
- Queue a project/source gate for selected device types and inspect its private
  archive → [Operator API and UI](lab-orchestrator/operator-api-and-ui/SPEC.md)
- Install, inspect, update, and roll back without mixing code, private state, or
  worker environments →
  [Service deployment](lab-orchestrator/service-deployment/SPEC.md)
- Install reviewed project guidance without overwriting unrelated local skills →
  [Repository skills](project-tooling/repository-skills/SPEC.md)
