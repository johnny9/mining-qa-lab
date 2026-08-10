# Service deployment — acceptance

## Functional behavior

- [x] **ORCH-SERVICE-AC-01:** The human runbook and agent skill explain initial
  installation, inspection, exact-SHA update, verification, rollback, and
  troubleshooting using one consistent release layout.
- [x] **ORCH-SERVICE-AC-02:** The example systemd user unit validates config before
  serve, restarts boundedly after failure, preserves graceful stop, protects the
  filesystem, and leaves required network/USB access available.
- [x] **ORCH-SERVICE-AC-03:** A read-only inspector reports unit state, optional
  candidate config validation, bounded API health, and safe-to-restart only when
  the service is active/healthy with zero observed running assignments.
- [x] **ORCH-SERVICE-AC-04:** Update instructions prepare and validate an exact
  candidate with repository/commit/tree provenance before an atomic observed-idle
  cutover, retain the previous release, and disclose the absent drain lock.
- [x] **ORCH-SERVICE-AC-05:** Rollback restores the retained previous release
  without deleting or rewriting private config, secrets, application state, or
  managed worker environments.

## Interfaces and compatibility

- [x] **ORCH-SERVICE-AC-06:** Config/env/state/release/worker paths and the service
  venv versus worker venv boundary are explicit and portable rather than tied to
  one user, device, address, or repository checkout.
- [x] **ORCH-SERVICE-AC-07:** Existing CLI, `/api/v1/health`, config, and SQLite
  contracts remain authoritative; deployment does not invent hidden app state.

## Quality attributes

- [x] **ORCH-SERVICE-AC-08:** Automated tests cover inspector bounds/failures,
  systemd template invariants, skill installation conflicts, links, and metadata.
- [x] **ORCH-SERVICE-AC-09:** Validation includes skill checks, systemd syntax,
  spec integrity, full unit tests, package build, and privacy/whitespace scans.
- [ ] **ORCH-SERVICE-AC-10:** The current lab host has completed an authorized
  exact-SHA install or update and rollback drill with zero interrupted work and
  post-restart service/config/state verification.

## Verification evidence

- 2026-08-10: The standalone lab's 48-test unit suite passed, including
  temporary-home installer conflicts, bounded inspector behavior, shared
  safety wording, systemd template invariants, and specification integrity.
- 2026-08-10: Repository skill validation, the standard skill quick validator,
  shell syntax for both documented command sets, `systemd-analyze verify`,
  wheel/sdist build, and `git diff --check` passed.
- No live service mutation, install, update, rollback, or HIL was performed;
  ORCH-SERVICE-AC-10 remains outstanding and host-specific.

## Acceptance rule

Source work is acceptable when AC-01 through AC-09 have current automated
evidence. Operational acceptance remains host-specific and requires AC-10 plus
explicit authorization; an API health response alone is insufficient.
