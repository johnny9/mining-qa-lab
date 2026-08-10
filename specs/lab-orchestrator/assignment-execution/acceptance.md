# Assignment execution — acceptance

## Functional behavior

- [x] **ORCH-EXEC-AC-01:** Execution requires all setup device leases and rejects
  disabled devices before launching the runner.
- [x] **ORCH-EXEC-AC-02:** Local and SSH invocations use captured profile/module/
  devices/PR policy, exact commit provenance, and bounded timeout.
- [x] **ORCH-EXEC-AC-03:** Environment is allowlisted plus explicit runner
  correlation variables; SSH agent forwarding is disabled.
- [x] **ORCH-EXEC-AC-04:** Worker log and bounded result pointer produce durable
  normalized assignment status, detail, and child ID/URL.

## Interfaces and compatibility

- [x] **ORCH-EXEC-AC-05:** Runner remains owner of test lifecycle, cleanup,
  artifacts, and detailed child publication.
- [x] **ORCH-EXEC-AC-06:** Missing/malformed pointer, timeout, SSH/process, or
  deployment failure cannot be recorded as passed.

## Quality attributes

- [x] **ORCH-EXEC-AC-07:** Unit tests cover command/environment/pointer, failure,
  lease, and child-link behavior.
- [ ] **ORCH-EXEC-AC-08:** Current local and configured SSH lab workers have
  completed assignments with verified cleanup and correlated child results.

## Verification evidence

- `tests.unit.test_orchestrator` covers local execution, metadata, pointer,
  leases, and child publication linkage; reconciled 2026-08-10.
- Live local/SSH HIL was not run for this documentation iteration.

## Acceptance rule

Execution-contract changes require producer/consumer unit tests and exact
command/environment assertions. Host transport or hardware-targeting changes
require the affected live path plus independent post-run device-state verification.
