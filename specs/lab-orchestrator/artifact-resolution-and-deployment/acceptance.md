# Artifact resolution and deployment — acceptance

## Functional behavior

- [x] **ORCH-DEPLOY-AC-01:** Resolution accepts only a successful configured
  workflow run whose head SHA exactly matches the gate commit.
- [x] **ORCH-DEPLOY-AC-02:** Download/extraction enforces byte bounds, safe member
  paths, exact artifact name/member, and digest policy.
- [x] **ORCH-DEPLOY-AC-03:** Deployment rejects board mismatch before OTA and
  verifies reboot/identity before success.
- [x] **ORCH-DEPLOY-AC-04:** A verified marker makes later assignments in the
  same gate/setup skip duplicate OTA while retaining provenance.

## Interfaces and compatibility

- [x] **ORCH-DEPLOY-AC-05:** GitHub credentials are not forwarded to signed
  storage URLs or written into metadata/logs.
- [x] **ORCH-DEPLOY-AC-06:** Failure before verification writes no success marker
  and makes the assignment error.

## Quality attributes

- [x] **ORCH-DEPLOY-AC-07:** Unit tests cover exact SHA, bounds, malicious ZIP,
  digest, board, OTA, reboot, and marker behavior.
- [ ] **ORCH-DEPLOY-AC-08:** Current target hardware has completed authorized
  OTA, post-reboot identity verification, testing, and recovery-path validation.

## Verification evidence

- `tests.unit.test_orchestrator_firmware` covers fetch/deploy security and
  idempotency; reconciled 2026-08-10.
- No physical OTA was performed for this documentation iteration.

## Acceptance rule

Fetch/cache-only changes need adversarial archive/auth tests. Any device write,
board policy, or reboot verification change requires authorized target HIL and
a proven recovery path before end-to-end acceptance.
