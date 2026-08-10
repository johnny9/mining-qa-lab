# Testcode bootstrap — acceptance

## Functional behavior

- [x] **ORCH-TESTCODE-AC-01:** Existing configuration remains disabled and
  compatible; enabled configuration requires a valid GitHub repository, branch,
  positive timeout, and absolute per-host checkout/venv paths.
- [x] **ORCH-TESTCODE-AC-02:** The first assignment for a gate/host resolves the
  latest configured branch to one exact SHA and atomically records it only after
  successful installation.
- [x] **ORCH-TESTCODE-AC-03:** Later assignments for the same gate/host reinstall
  and verify the pinned SHA even when the branch has moved.
- [x] **ORCH-TESTCODE-AC-04:** A clean matching managed checkout is cloned or
  fetched at the exact SHA and installed editable into its isolated venv.
- [x] **ORCH-TESTCODE-AC-05:** Executor launches the installed runner, resolves
  relative profiles inside its checkout, and includes exact testcode metadata.

## Interfaces and compatibility

- [x] **ORCH-TESTCODE-AC-06:** Local commands are shell-free; SSH disables agent
  forwarding and quotes every remote argument.
- [x] **ORCH-TESTCODE-AC-07:** Wrong origin, tracked changes, corrupt marker,
  install/import failure, or runner repository/SHA mismatch fails before
  firmware deployment or hardware test construction.
- [x] **ORCH-TESTCODE-AC-08:** The active orchestrator environment is never used
  as the managed runner venv, and disabled hosts retain configured executable behavior.

## Quality attributes

- [x] **ORCH-TESTCODE-AC-09:** Unit tests cover configuration, resolution,
  marker reuse, command construction, safety failures, executor integration,
  and runner mismatch.
- [ ] **ORCH-TESTCODE-AC-10:** Current local and configured SSH workers have
  installed a real latest branch, reported its exact SHA, and completed a
  cleanup-verified assignment.

## Verification evidence

- `tests.unit.test_orchestrator_testcode`, `tests.unit.test_orchestrator`, and
  `tests.unit.test_config` cover AC-01 through AC-09; reconciled 2026-08-10.
- The full 91-test unit suite, five-test spec-integrity module, example YAML
  validation, wheel/sdist build, and `git diff --check` passed 2026-08-10.
- Live local/SSH installation and HIL were not authorized by this feature
  implementation request, so AC-10 remains unchecked.

## Acceptance rule

The feature is code-acceptable when AC-01 through AC-09 have current automated
evidence plus full unit/package/spec checks. Operational acceptance for a host
requires AC-10 with explicit authorization and independent cleanup verification.
