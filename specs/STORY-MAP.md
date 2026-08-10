# Story map

This map navigates by stakeholder outcome. [INDEX.md](INDEX.md) remains the
complete feature directory.

## Define and select trustworthy tests

- A developer can select devices, patterns, and PR-specific validation cases →
  [Configuration and selection](test-runner/configuration-and-selection/SPEC.md)
- A generic test can require behavior without naming a model →
  [Device capability contract](test-runner/device-capability-contract/SPEC.md)
- A maintainer can add an ESP-Miner model without forking generic tests →
  [ESP-Miner device adapters](test-runner/esp-miner-device-adapters/SPEC.md)

## Exercise hardware safely

- A test can mutate a miner and restore it after any outcome →
  [Lifecycle and cleanup](test-runner/lifecycle-and-cleanup/SPEC.md)
- A device can be observed over bounded concurrent interfaces →
  [Transport interfaces](test-runner/transport-interfaces/SPEC.md)
- An operator can target explicit firmware and verify the rebooted version →
  [Firmware lifecycle](test-runner/firmware-lifecycle/SPEC.md)

## Produce protocol and mining evidence

- A reviewer can see stable normalized mining health and event markers →
  [State, telemetry, and charting](test-runner/state-telemetry-and-charting/SPEC.md)
- A developer can verify public-pool reachability and live mining →
  [Public pool smoke](test-runner/public-pool-smoke/SPEC.md)
- A parser or client change can be exercised against deterministic Stratum
  framing and work →
  [Stratum V1 regression](test-runner/stratum-v1-regression/SPEC.md)

## Preserve and publish trustworthy results

- A reviewer can inspect evidence without receiving private lab identities →
  [Artifacts, privacy, and provenance](test-runner/artifacts-privacy-and-provenance/SPEC.md)
- Automation can consume one result model through local and remote publishers →
  [Result model and publishing](test-runner/result-model-and-publishing/SPEC.md)

## Turn authorized changes into durable lab work

- An operator can maintain one validated revisioned lab configuration →
  [Configuration and control plane](lab-orchestrator/configuration-and-control-plane/SPEC.md)
- Trusted events and exact-SHA approvals can enter without broadening authority →
  [Event ingestion and trust](lab-orchestrator/event-ingestion-and-trust/SPEC.md)
- A gate can expand into deterministic compatible work and retire stale queued
  PR heads →
  [Gate planning and supersession](lab-orchestrator/gate-planning-and-supersession/SPEC.md)
- Device use remains exclusive and recoverable across service restarts →
  [Persistence, leases, and recovery](lab-orchestrator/persistence-leases-and-recovery/SPEC.md)

## Operate the lab and aggregate outcomes

- An operator can inspect hosts, USB, devices, setups, and preflight failures →
  [Lab inventory and preflight](lab-orchestrator/lab-inventory-and-preflight/SPEC.md)
- A gate can deploy the exact successful artifact to the expected board →
  [Artifact resolution and deployment](lab-orchestrator/artifact-resolution-and-deployment/SPEC.md)
- A worker can install the latest approved testcode branch while retaining one
  exact harness revision across a gate →
  [Testcode bootstrap](lab-orchestrator/testcode-bootstrap/SPEC.md)
- A compatible host can execute the correct test module locally or over SSH →
  [Assignment execution](lab-orchestrator/assignment-execution/SPEC.md)
- Stakeholders can see one aggregate gate linked to detailed child evidence →
  [Parent gate publication](lab-orchestrator/parent-gate-publication/SPEC.md)
- A lab operator can use REST or focused pages without exposing an unsafe
  mutation surface →
  [Operator API and UI](lab-orchestrator/operator-api-and-ui/SPEC.md)
