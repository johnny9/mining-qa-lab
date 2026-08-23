# Central coordination agent — acceptance

## Functional behavior

- [x] **ORCH-CENTRAL-AC-01:** `local` and `central` are explicit validated modes;
  centrally supplied definitions cannot silently merge with local ownership.
- [x] **ORCH-CENTRAL-AC-02:** Registration, heartbeat, subscriptions, pull,
  claim, renewal, decline, and completion implement the exact Status/Lab v2
  contract.
- [x] **ORCH-CENTRAL-AC-03:** A central execution is persisted uniquely before
  claim and replay/restart cannot create duplicate local work.
- [x] **ORCH-CENTRAL-AC-04:** One portable requirement resolves to exactly one
  enabled private binding and re-runs local trust, compatibility, preflight,
  and lease checks.
- [x] **ORCH-CENTRAL-AC-05:** Assignment retry creates a new immutable attempt;
  prior status, timing, pointer, child links, archive, and cleanup disposition
  are never overwritten.
- [x] **ORCH-CENTRAL-AC-06:** Active work renews its claim; central loss or
  expiry never interrupts runner cleanup or causes automatic duplicate work.

## Interfaces and compatibility

- [x] **ORCH-CENTRAL-AC-07:** Lab and Status validate byte-identical
  `lab-coordination-v2` contracts; Lab and Testcode validate byte-identical
  `orchestration-v2` contracts.
- [x] **ORCH-CENTRAL-AC-08:** Lab reads v1 and v2 runner pointers before central
  mode writes v2 metadata, and local-mode v1 behavior remains compatible.
- [x] **ORCH-CENTRAL-AC-09:** Completion carries the exact global, Lab, local,
  assignment, attempt, runner, definition, source, and Testcode correlation
  allowed by the public/private split.

## Quality attributes

- [x] **ORCH-CENTRAL-AC-10:** Allowlist serializers prove no local device/setup/
  profile identity, coordinate, credential, path, pool/payout identity, raw
  log, claim token, or cleanup diagnostic enters public completion.
- [x] **ORCH-CENTRAL-AC-11:** DTOs, cursor, outbox, claims, backoff, bodies,
  errors, lists, attempts, and retained events are bounded and restart tested.
- [x] **ORCH-CENTRAL-AC-12:** The Status-owned two-Lab suite passes replay,
  expiry, restart, late completion, malformed input, privacy, and cleanup-error
  scenarios without real hardware or external publication.

## Verification evidence

- `PYTHONPATH=src python -m unittest discover -s tests/unit -v` completed 72
  tests on 2026-08-16 (63 passed, nine optional web tests skipped in the lean
  local interpreter); the Status-owned process suite separately exercised the
  real Lab web/CLI boundary.
- `tests.unit.test_central_coordination` covers strict mode/binding validation,
  canonical offer rejection, atomic cursor replay, SQLite reopen, immutable
  attempt identity, and durable outbox state.
- The Status-owned nine-scenario development simulation passed two independent
  Lab configs/tokens/SQLite databases through replay, expiry, restart, late
  completion, malformed input, privacy, and cleanup error.
- Focused central tests cover exact binding snapshots, repository/SHA and
  loopback preflight, exclusive resource conflicts, immutable retry attempts,
  maximum attempt enforcement, active-run renewal without cleanup interruption,
  resource release on failed claim paths, persisted pause/failure/backoff state,
  heartbeat cadence, and restart recovery. The CLI and service expose the
  continuous agent loop plus authenticated status/pause/resume controls.

## Acceptance rule

Enable central mode only after v2 readers exist on both boundaries, persistence
and privacy regressions pass, the complete local scenario matrix passes, and
the mode remains disabled by default for real configurations.
