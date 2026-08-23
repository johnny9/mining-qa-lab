# Distributed advisory QA — lab service delivery plan

Status: implemented proof-of-concept delivery record; durable specs are authoritative

Updated: 2026-08-16

Related plans:

- [Status service](../../mining-qa-status/plans/distributed-advisory-qa.md)
- [Test runner](../../mining-qa-testcode/plans/distributed-advisory-qa.md)

Durable contracts and acceptance now live in:

- [Central coordination agent](../specs/lab-orchestrator/central-coordination-agent/SPEC.md)
- [Status/Lab coordination v2](../contracts/lab-coordination-v2.md)
- [Lab/Testcode orchestration v2](../contracts/orchestration-v2.md)

This file records the original delivery sequence and its reconciliation. The
linked feature specs and versioned contracts are normative. QAUI PNGs are
non-normative information-design references; implemented agent health uses
`ok`, `degraded`, `paused`, and `error` and does not define the concept-only
`Maintenance` state.

## Goal

Evolve `mining-qa-lab` from the owner of triggers, gates, suites, and global
gate aggregation into a private lab agent that registers its interests, pulls
portable execution requests, binds them to local resources, and publishes one
per-lab execution summary.

The lab remains the final safety and authorization boundary. Central
coordination never leases a device, selects a credential, issues a hardware
command, approves firmware, or treats service state as proof of cleanup.

## Agreed product decisions

- Every eligible subscribed lab should run a matching gate initially.
- Gates are advisory to maintainers, not strict blockers.
- The coordination service freezes the eligible lab set at trigger time.
- The lab advertises only sanitized capability and coarse capacity data.
- Portable suite requirements are mapped through private local bindings.
- Work is pulled outbound by the lab and claimed with a renewable lease.
- The lab publishes per-lab execution state and child-result links; global
  coverage and advisory assessment are owned centrally.
- The central service may expose sanitized per-lab/platform outcomes through
  public read-only status views, but never exposes local bindings or permits an
  anonymous control action.
- Existing local orchestration remains an explicit mode during migration.

## Target boundary

### The lab continues to own

- Local operator authorization and network exposure.
- Private hosts, setups, device identities, credentials, and profiles.
- Compatibility validation, probes, preflight, and exclusive resource leases.
- Exact runner installation, optional verified firmware deployment, process
  execution, timeout, private worker/orchestrator logs, recovery, and
  cancellation. Runner-produced post-run sanitized logs may be published by
  testcode as detailed child evidence.
- Local assignment state, attempt history, private artifact redundancy, and
  child-result linking.
- Proof that runner cleanup completed; lease release alone is not proof.

### The lab stops owning in central mode

- Canonical project, suite, gate, and trigger definitions.
- The global eligible-lab set.
- Global gate lifecycle, coverage, or advisory assessment.
- Cross-lab rerun, quorum, cost, and prioritization policy.

### The runner continues to own

- Test discovery and selection validation.
- Device lifecycle and cleanup.
- Detailed outcomes, telemetry, artifacts, privacy, provenance, and detailed
  child publication.

## Proof-of-concept outcome

One lab process runs in explicit `central` mode against local Status. It
registers a coordination identity, sends a heartbeat and subscriptions, pulls
a single manual gate execution, claims it, resolves one portable requirement
through a private synthetic binding, runs Testcode against a mock Gamma/fake
Stratum process, renews the claim, and submits a per-lab summary with child
links.

A second deterministic simulated lab demonstrates redundant dispatch without
requiring a second physical host. No real hardware, firmware, source download,
SSH, service deployment, or external publication occurs.

## Configuration model

Add an explicit mode rather than inferring behavior from the presence of a URL:

```yaml
coordination:
  mode: local # local | central
  central:
    base_url: https://public.example
    lab_id: lab-east
    token_env: MINING_QA_LAB_AGENT_TOKEN
    heartbeat_seconds: 30
    poll_seconds: 10
    claim_ttl_seconds: 120
    retry_backoff_seconds: 2
    max_backoff_seconds: 60
    max_attempts: 3
    subscriptions:
      gates: [firmware-advisory]

bindings:
  suite_requirements:
    gamma-http-and-stratum:
      profile: /private/profiles/gamma-read-write.toml
      testcode_root: /private/checkouts/mining-qa-testcode
      testcode_commit: 0123456789abcdef0123456789abcdef01234567
      platform_class: gamma
      device_model: gamma-602
      capabilities: [http, stratum-v1]
      resources: [gamma-bench]
```

The checked-in example uses placeholders only. The long-lived Lab bearer token
is read from a named environment variable and is never written to YAML, SQLite,
logs, subprocess arguments, metadata, or results. A short-lived claim
capability may be retained only in the private mode-0600 SQLite state required
for crash-safe renewal/completion; it is cleared at terminal disposition and
never logged, placed in YAML, passed to Testcode, or published.

`local` mode retains current local triggers, planning, and parent publication.
`central` mode rejects ambiguous simultaneous ownership: centrally supplied
definitions create central executions, while existing local events create only
local runs. The UI and API label the origin on every record.

## Coordination registration document

The lab may send through an authenticated service-to-service route:

- stable coordination lab ID and display name;
- agent and supported protocol versions;
- sanitized capability keys such as platform family, transport kind, or test
  feature;
- coarse available slot count;
- subscription IDs;
- heartbeat time and bounded health reason codes.

Public status is grouped by non-identifying platform/model class. The lab does
not create or send a stable public alias for a physical miner. Heartbeats may
attach one aggregate state (`available`, `busy`, `offline`, `stale`, or
`unknown`) and evidence timestamp per class; they never expose a unit count
small enough to identify one miner, lease owners, queue depth, exact capacity,
or probe details.

It must not send local device names/IDs, serial numbers, USB identifiers or
paths, MAC/IP addresses, device hostnames/URLs, mDNS names, Bitcoin or payout
addresses, pool usernames/worker identities, local profile/setup IDs,
filesystem paths, credentials, raw probe output, raw logs, or resolved
environment values. A single allowlist serializer should construct this
document; do not serialize internal models and subtract fields.

## Portable requirements and private bindings

A central suite revision supplies a bounded portable requirement document, for
example:

```json
{
  "requirement_id": "gamma-http-and-stratum",
  "platform_family": "gamma-600",
  "capabilities": ["http", "stratum-v1"],
  "test_pattern": "test_public_pool_smoke"
}
```

The local binding resolves the requirement to an existing setup, runner
profile, optional firmware policy, and devices. Resolution rules:

1. Validate the central definition revision and digest.
2. Resolve exactly one enabled binding by stable requirement ID.
3. Re-run current local compatibility and trust checks.
4. Freeze a private execution snapshot before acquiring resources.
5. Fail the lab execution as unavailable with a bounded sanitized reason when no
   safe binding exists.
6. Never return the private binding contents to the coordination service.

Capability advertisement is only an eligibility hint. It does not bypass local
binding, policy, freshness, preflight, or lease checks.

## Agent protocol and state

### Outbound flow

1. Register or validate the configured coordination lab ID.
2. Heartbeat sanitized capability, capacity, and subscription state.
3. Pull bounded offers after a durable cursor.
4. Validate protocol version, definition digest, source identity, deadline,
   and portable requirements before claiming.
5. Claim atomically and persist the central execution ID and lease before local
   planning.
6. Resolve bindings and create the local assignment matrix idempotently.
7. Renew the central claim while local work is active.
8. Execute through the versioned runner boundary.
9. Persist local outcomes and cleanup evidence before releasing resources.
10. Submit one sanitized per-lab completion with immutable child links.

The completion is a sanitized published status record and may include the
public lab identity, non-identifying platform/model class, outcome, timestamps,
project, repository and revision, trigger, gate/suite revision, exact testcode
source, stable opaque run correlation IDs, and child-result links. It never
contains a physical-device alias or identifier. It must be safe to return in
full without per-reader field removal. Registration, credentials, heartbeat
diagnostics, exact capacity, subscriptions, claims, leases, private local-run
or device identity, cleanup internals, and diagnostics are sent through
separate authenticated coordination records and are never embedded in the
published status record.

The lab never promotes its raw process, SSH, or orchestrator logs to public
evidence. It may retain or archive both the runner's raw private log and its
post-run sanitized public copy as distinct hash-verified artifacts. Only the
testcode-produced sanitized copy and its public result link may appear in the
published completion.

Public run correlation IDs are generated independently and never derived from
a local device ID, address, serial number, pool user, or other device identity.

### Required identifiers

- `central_gate_run_id`: global authenticated evidence container.
- `lab_execution_id`: this lab's global execution record.
- `local_gate_run_id`: private durable lab record.
- `assignment_id`: one local runner invocation.
- `attempt_id`: one immutable attempt of an assignment.
- `definition_digest`: exact portable input.

These identifiers are never substituted for one another. The local database
must enforce uniqueness on the central execution ID so offer replay cannot
duplicate hardware work.

### State model

Use the exact related execution, immutable claim-generation, local execution,
assignment-attempt, and outbox state machines in
[Status/Lab coordination v2](../contracts/lab-coordination-v2.md) and the
[central-agent design](../specs/lab-orchestrator/central-coordination-agent/design.md).

A temporary loss of central connectivity does not interrupt active hardware
cleanup. The lab persists a bounded outbox and retries only idempotent heartbeat,
renewal, and completion operations. If the claim expires during an active run,
the lab finishes cleanup, retains evidence, and reports a late-completion
conflict for operator review; it never starts a duplicate assignment merely to
repair coordination state.

## Implemented persistence prerequisite: immutable attempts

The implementation adds an `assignment_attempts` table keyed by immutable
`attempt_id`, with
attempt number, status, timestamps, bounded detail, runner pointer metadata,
child result ID/URL, archive metadata, and cleanup disposition. The assignment
row becomes the stable work identity and exposes only current/aggregate state.
Retry creates a new attempt; it never overwrites a terminal attempt. Startup
migration backfills existing assignment evidence into attempt 1; reopen,
rollback, recovery, and retry behavior are covered by unit tests.

## API and service changes

- Add a central-agent client isolated from existing event-feed and result
  publication clients.
- Add bounded DTOs and validation for registration, heartbeat, offers, claims,
  renewals, completions, and protocol errors.
- Use distinct DTOs for sanitized published completion/status records and
  private coordination records; never serialize an internal object and remove
  fields according to the reader.
- Add durable tables for central executions, offer cursor, claim lease, outbox,
  definition snapshot, private binding snapshot, and immutable attempts.
- Add an engine loop for heartbeat/pull/renew/outbox alongside the existing
  worker loop, with independent timeouts and backoff.
- Add operator actions to pause new central claims without interrupting active
  cleanup, retry safe outbox entries, and disable a subscription locally.
- Preserve local API authentication, network restrictions, ETags, and bounded
  responses.

## Operator views

Use
[`04-lab-operations-v2.png`](../../artifacts/mining-qa-poc-ui/04-lab-operations-v2.png)
as the information model:

- central connection and protocol health;
- coordination registration and heartbeat state;
- active subscriptions and advertised sanitized capabilities;
- offers, claims, lease expiry, and outbox state;
- central execution to local run correlation;
- local bindings, resources, workers, assignments, attempts, and cleanup state;
- private details visible only inside the restricted lab UI.

The page must clearly distinguish central coordination state from local
hardware truth. A green heartbeat cannot imply that a device is safe or clean.

## Delivery sequence

Each step should be an independently reviewable change.

1. **Durable intent.** Implement against the indexed central-agent spec and the
   two coordinated v2 contracts; keep affected current specs synchronized.
2. **Attempt normalization.** Add the assignment-attempt migration and refactor
   retry, recovery, archival, UI, and tests to preserve all terminal evidence.
3. **Versioned contract reader.** Accept the next runner metadata/result-pointer
   contract while continuing to read version 1. Do not emit the new version
   yet.
4. **Central client models.** Implement allowlisted coordination registration,
   heartbeat, subscription, offer, claim, renewal, decline, completion, and
   error DTOs with malformed/bounded/privacy tests.
5. **Durable agent state.** Add central execution, cursor, lease, definition
   snapshot, binding snapshot, and outbox storage with idempotence and reopen
   tests.
6. **Binding and planning.** Resolve one portable requirement to one private
   fake setup and create a local matrix without exposing the binding.
7. **Agent loop.** Implement outbound heartbeat, pull, claim, renew, completion,
   pause, expiry, restart recovery, and bounded backoff.
8. **Runner writer.** After the runner accepts the new contract, emit the new
   correlation metadata for centrally originated assignments.
9. **Operator API and UI.** Add the connection, execution, binding, resource,
    attempt, and cleanup views without weakening existing auth or network rules.
10. **Simulation.** Run the Status-owned deterministic two-Lab proof of concept
    with the real Gamma adapter against isolated mock-device processes and
    record state-transition, cleanup, correlation, and privacy evidence.

## Proof-of-concept acceptance

- [x] `local` and `central` are explicit, validated modes with no silent merge
  of definition ownership.
- [x] Registration and every heartbeat contain only allowlisted sanitized data.
- [x] The lab pulls and claims one matching offer exactly once across replay and
  restart.
- [x] An unmatched or unsafe private binding declines work without touching
  hardware.
- [x] A matched fake binding creates a durable local execution/attempt, acquires
  its private resources, and renews its claim while simulated work is active.
- [x] Completion contains the correct global, lab-execution, local-run,
  assignment, attempt, and definition identities plus child links.
- [x] Public device evidence is grouped by platform/model class and exposes no
  stable physical-device alias, local device/setup/profile identity, topology,
  address, pool identity, credential, or per-unit operational state.
- [x] The published completion contains full non-secret source provenance and
  is safe to expose unchanged; claim, lease, diagnostic, and private local
  state are stored separately.
- [x] Raw worker/orchestrator logs remain private; a published child log is a
  distinct testcode-sanitized artifact with no device identifier.
- [x] Central loss or lease expiry never interrupts cleanup or causes duplicate
  local work.
- [x] Retry preserves every previous attempt and its evidence.
- [x] Existing local-mode unit behavior remains compatible.
- [x] No real network target, firmware, SSH worker, device, deployment, or
  publication is used.

## Verification

Implementation requires focused protocol/privacy/state tests, followed by:

```text
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v
python3 -m build --no-isolation
git diff --check
```

The simulation must include duplicate offer delivery, competing claim, claim
renewal, service restart, central outage during cleanup, malformed definition,
private-field rejection, and late completion. Hardware qualification remains a
separate later authorization.

## Later phases, not part of the proof of concept

- Real lab enrollment and staged shadow mode.
- Central repository-event and scheduled triggers.
- Multiple bindings per portable requirement and operator selection policy.
- Cost/capacity-aware subscription controls.
- Rerun requests and immutable cross-lab attempt comparison.
- Deprecation of local trigger/gate/suite ownership after export, conflict
  review, rollback proof, and an announced compatibility window.

## Rollback and migration rule

Central mode remains disabled by default. Its tables, client loop, and pages
must be independently disableable without changing local-mode planning or
runner safety. Existing local definitions are not automatically uploaded,
deleted, or reinterpreted. Any later import is an explicit reviewed migration
with stable ID mapping and a reversible export.
