# Central coordination agent — acceptance

## Functional behavior

- [x] **ORCH-CENTRAL-AC-01:** `local`, `central`, and `hybrid` are explicit
  validated modes. Hybrid runs central and local workers together while shared
  and local definition identities remain separate.
- [x] **ORCH-CENTRAL-AC-02:** Registration, heartbeat, subscriptions, pull,
  claim, renewal, decline, and completion implement the exact Status/Lab v2
  contract.
- [x] **ORCH-CENTRAL-AC-03:** A central execution is persisted uniquely before
  claim and replay/restart cannot create duplicate local work.
- [x] **ORCH-CENTRAL-AC-04:** Every portable requirement resolves to exactly one
  enabled private binding and re-runs local trust, compatibility, preflight,
  and lease checks; a missing or ambiguous binding declines the whole offer
  before runner access.
- [x] **ORCH-CENTRAL-AC-05:** Assignment retry creates a new immutable attempt;
  prior status, timing, pointer, child links, archive, and cleanup disposition
  are never overwritten.
- [x] **ORCH-CENTRAL-AC-06:** Active work renews its claim; central loss or
  expiry never interrupts runner cleanup or causes automatic duplicate work.
- [x] **ORCH-CENTRAL-AC-13:** Every private binding explicitly selects `mock`
  or `hardware`; mock execution requires a loopback endpoint, while hardware
  execution requires an absolute executable, explicit private runner devices,
  exact clean Testcode checkout, bounded timeout, and exclusive resources.
- [x] **ORCH-CENTRAL-AC-14:** Hardware execution passes the frozen portable test
  pattern plus only the binding's private device selectors, uses an allowlisted
  environment, bounds process output while it runs, and produces the exact v2
  pointer/completion without integration-only variables or reset calls.
- [x] **ORCH-CENTRAL-AC-15:** A failure after hardware runner launch is terminal
  and records bounded local evidence/cleanup uncertainty without automatic
  hardware retry; a sanitized central error completion is attempted when no
  valid child pointer exists.

## Interfaces and compatibility

- [x] **ORCH-CENTRAL-AC-07:** Lab and Status validate byte-identical
  `lab-coordination-v2` contracts; Lab and Testcode validate byte-identical
  `orchestration-v2` contracts.
- [x] **ORCH-CENTRAL-AC-08:** Lab reads v1 and v2 runner pointers before central
  mode writes v2 metadata, and local-mode v1 behavior remains compatible.
- [x] **ORCH-CENTRAL-AC-09:** Completion carries the exact global, Lab, local,
  assignment, attempt, runner, definition, source, and Testcode correlation
  allowed by the public/private split.
- [x] **ORCH-CENTRAL-AC-16:** `serve` runs one persistent central loop with
  heartbeat cadence, pause/backoff state, graceful shutdown, and health status;
  the local operator surface directs central manual runs to Status.
- [x] **ORCH-CENTRAL-AC-17:** An enrollment command reads one app-issued Lab
  token from the configured environment, binds it centrally, and creates a
  mode-0600 environment file without printing or storing it in YAML or logs.
- [x] **ORCH-CENTRAL-AC-18:** The same scoped Lab token authenticates central
  coordination and is passed to the trusted exact-SHA Testcode process as its
  `MINING_QA_TOKEN` result/artifact publisher token; unrelated credentials and
  the service-side token-variable name remain filtered.
- [x] **ORCH-CENTRAL-AC-19:** One claimed execution runs the frozen requirements
  in suite order, creates a stable assignment and immutable retry attempts per
  requirement, resumes only unfinished requirements after restart, and submits
  one completion containing one child for every selected module.
- [x] **ORCH-CENTRAL-AC-20:** Catalog-backed requirements carry exact Testcode
  repository/commit provenance, module ID, and only declared bounded portable
  options. The Lab rejects provenance drift, forwards the selection in a
  dedicated runner contract value, and Testcode revalidates before device use.
- [x] **ORCH-CENTRAL-AC-21:** An authenticated local operator in hybrid mode can
  request a shared manual gate through the existing Lab-bound token. Status
  may target only that same Lab; the request cannot fan out or name another Lab.

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

- The complete Lab unit suite passed all 87 tests on 2026-08-27. Central-agent
  tests prove exact catalog/binding repository and commit agreement, bounded
  module/option forwarding, acceptance of automatic trigger provenance, and
  rejection of private-looking options before runner launch.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v`
  passed all 86 tests on 2026-08-27. Multi-module coverage proves immutable
  binding plans, stable per-requirement assignment identity, per-assignment
  retry bounds, restart resume without rerunning a completed module, ordered
  execution, and aggregate completion with one child per module.
- The wheel/sdist build and all five repository skill validators passed on
  2026-08-27. Status-owned simulation run `20260827T135058.254730Z` passed all
  nine scenarios with two modules per complete Lab execution; it is simulation,
  not HIL.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v`
  passed all 84 tests on 2026-08-27 after the unified-token change. The focused
  central suite proves mode-0600 binding, token reuse for trusted Testcode
  publication, unrelated-secret filtering, replay, renewal, and recovery.
- The package wheel/sdist build, specification integrity, and all repository
  skill validators passed on 2026-08-27.
- Status-owned development simulation run `20260827T030847.651096Z` passed all
  nine scenarios with one app-issued token per Lab for registration,
  coordination, child publication, and artifacts; it is simulation, not HIL.
- `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v`
  completed all 84 Lab tests on 2026-08-24 with no skips, including the real
  optional web/service boundary.
- `tests.unit.test_central_coordination` covers strict mode/binding validation,
  canonical offer rejection, atomic cursor replay, SQLite reopen, immutable
  attempt identity, and durable outbox state.
- The Status-owned nine-scenario development simulation passed two independent
  Lab configs/tokens/SQLite databases through replay, expiry, restart, late
  completion, malformed input, privacy, and cleanup error in run
  `20260824T095559.777660Z`. Rootless isolation, one-use enrollment,
  idempotent registration replay, and scoped teardown passed; the
  evidence is explicitly simulation and not HIL. The current credential model
  uses one app-issued token per simulated Lab for coordination and publication.
- Focused central tests cover exact binding snapshots, repository/SHA and
  loopback preflight, exclusive resource conflicts, immutable retry attempts,
  maximum attempt enforcement, active-run renewal without cleanup interruption,
  resource release on failed claim paths, persisted pause/failure/backoff state,
  heartbeat cadence, and restart recovery. The CLI and service expose the
  continuous agent loop plus authenticated status/pause/resume controls.
- Production-binding tests additionally cover exact clean-checkout/executable/
  profile preflight, allowlisted hardware commands and environments, bounded
  streaming output, v2 pointer validation, terminal post-launch failure,
  sanitized completion, mode-0600 enrollment, and durable binding snapshots.

## Acceptance rule

Enable central mode only after v2 readers exist on both boundaries, persistence
and privacy regressions pass, the complete local scenario matrix passes, and a
real binding passes configuration/preflight. Calling a physical Lab operational
additionally requires authorized HIL and independent cleanup verification.
