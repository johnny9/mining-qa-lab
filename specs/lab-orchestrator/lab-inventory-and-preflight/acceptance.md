# Lab inventory and preflight — acceptance

## Functional behavior

- [x] **ORCH-LAB-AC-01:** Hosts, devices, setups, role mappings, profiles, and
  coordinates are cross-validated before activation.
- [x] **ORCH-LAB-AC-02:** Host/device/USB probes and setup preflight return
  bounded per-check outcomes without changing device state.
- [x] **ORCH-LAB-AC-03:** Disabled or missing required devices make preflight
  fail explicitly.
- [x] **ORCH-LAB-AC-04:** Photo responses are restricted to configured sources,
  media expectations, and size limits.

## Interfaces and compatibility

- [x] **ORCH-LAB-AC-05:** Stable logical labels are separated from private API
  addresses and serial paths.
- [x] **ORCH-LAB-AC-06:** Preflight reports observation only and does not claim
  runner capability, mining health, or lease ownership.

## Quality attributes

- [x] **ORCH-LAB-AC-07:** Probe network/process operations have time/output
  bounds and failure isolation.
- [ ] **ORCH-LAB-AC-08:** Every configured production setup currently passes
  live API, USB identity, and compatibility preflight.

## Verification evidence

- `tests.unit.test_orchestrator_web` and configuration tests cover API routes,
  inventory validation, and probe/preflight behavior; reconciled 2026-08-10.
- The live lab inventory was not fully probed for this documentation iteration.

## Acceptance rule

Schema/probe changes require invalid, timeout, and privacy tests. A setup cannot
be called operational until a current live preflight is recorded; mutation must
remain outside preflight.
