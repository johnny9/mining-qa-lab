# Assignment execution — acceptance

## Functional behavior

- [x] **ORCH-EXEC-AC-01:** Execution requires all setup device leases and rejects
  disabled devices before launching the runner.
- [x] **ORCH-EXEC-AC-02:** Local and SSH invocations use captured profile/module/
  devices/PR policy, exact commit provenance, and bounded timeout.
- [x] **ORCH-EXEC-AC-03:** Environment is allowlisted plus explicit runner
  correlation variables; SSH agent forwarding is disabled.
- [x] **ORCH-EXEC-AC-04:** Worker log and the version-1, 64-KiB-bounded result
  pointer produce durable normalized assignment status, detail, and child URL/ID.

## Interfaces and compatibility

- [x] **ORCH-EXEC-AC-05:** Runner remains owner of test lifecycle, cleanup,
  artifacts, and detailed child publication.
- [x] **ORCH-EXEC-AC-06:** Missing/malformed/oversized/unsupported-version
  pointer, timeout, SSH/process, or deployment failure cannot be recorded as
  passed.
- [x] **ORCH-EXEC-AC-09:** A supplied manifest is bounded and every archived
  local/SSH artifact is path-, size-, and SHA-256-verified into attempt-specific
  private storage; legacy pointers may omit it.
- [x] **ORCH-EXEC-AC-10:** With Mining QA Status enabled, a successful runner
  without a published child identity becomes an assignment error even if local
  artifacts are available.

## Quality attributes

- [x] **ORCH-EXEC-AC-07:** Unit tests cover command/environment/pointer, failure,
  lease, and child-link behavior.
- [ ] **ORCH-EXEC-AC-08:** Current local and configured SSH lab workers have
  completed assignments with verified cleanup and correlated child results.

## Verification evidence

- `tests.unit.test_orchestrator` covers local execution, versioned metadata,
  bounded/unsupported pointer handling, optional installed runner ordering,
  leases, and child publication linkage; reconciled 2026-08-10.
- `tests.unit.test_orchestrator_archive` covers local and bounded SSH retrieval,
  tamper rejection, and hash-verified storage; reconciled 2026-08-10.
- Live local/SSH HIL was not run for this documentation iteration.

## Acceptance rule

Execution-contract changes require producer/consumer unit tests and exact
command/environment assertions. Host transport or hardware-targeting changes
require the affected live path plus independent post-run device-state verification.
