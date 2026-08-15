# Central coordination agent — acceptance

## Functional behavior

- [ ] **ORCH-CENTRAL-AC-01:** `local` and `central` are explicit validated modes;
  centrally supplied definitions cannot silently merge with local ownership.
- [ ] **ORCH-CENTRAL-AC-02:** Registration, heartbeat, subscriptions, pull,
  claim, renewal, decline, and completion implement the exact Status/Lab v2
  contract.
- [ ] **ORCH-CENTRAL-AC-03:** A central execution is persisted uniquely before
  claim and replay/restart cannot create duplicate local work.
- [ ] **ORCH-CENTRAL-AC-04:** One portable requirement resolves to exactly one
  enabled private binding and re-runs local trust, compatibility, preflight,
  and lease checks.
- [ ] **ORCH-CENTRAL-AC-05:** Assignment retry creates a new immutable attempt;
  prior status, timing, pointer, child links, archive, and cleanup disposition
  are never overwritten.
- [ ] **ORCH-CENTRAL-AC-06:** Active work renews its claim; central loss or
  expiry never interrupts runner cleanup or causes automatic duplicate work.

## Interfaces and compatibility

- [ ] **ORCH-CENTRAL-AC-07:** Lab and Status validate byte-identical
  `lab-coordination-v2` contracts; Lab and Testcode validate byte-identical
  `orchestration-v2` contracts.
- [ ] **ORCH-CENTRAL-AC-08:** Lab reads v1 and v2 runner pointers before central
  mode writes v2 metadata, and local-mode v1 behavior remains compatible.
- [ ] **ORCH-CENTRAL-AC-09:** Completion carries the exact global, Lab, local,
  assignment, attempt, runner, definition, source, and Testcode correlation
  allowed by the public/private split.

## Quality attributes

- [ ] **ORCH-CENTRAL-AC-10:** Allowlist serializers prove no local device/setup/
  profile identity, coordinate, credential, path, pool/payout identity, raw
  log, claim token, or cleanup diagnostic enters public completion.
- [ ] **ORCH-CENTRAL-AC-11:** DTOs, cursor, outbox, claims, backoff, bodies,
  errors, lists, attempts, and retained events are bounded and restart tested.
- [ ] **ORCH-CENTRAL-AC-12:** The Status-owned two-Lab suite passes replay,
  expiry, restart, late completion, malformed input, privacy, and cleanup-error
  scenarios without real hardware or external publication.

## Verification evidence

- `tests.unit.test_specs` validates this proposed feature's structure and
  links; expected after the documentation change.
- Central-agent, database, protocol, process, and integration behavior are not
  implemented; those criteria remain unchecked.

## Acceptance rule

Enable central mode only after v2 readers exist on both boundaries, persistence
and privacy regressions pass, the complete local scenario matrix passes, and
the mode remains disabled by default for real configurations.
