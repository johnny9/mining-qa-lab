# Event ingestion and trust — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| GitHub client | Fetch branch/PR/compare facts with bounded API calls | `src/mining_qa_lab/events.py` |
| QA feed client | Consume ordered delivery records from Mining QA Status | `src/mining_qa_lab/events.py` |
| Event collector | Apply policy and create normalized source events | `src/mining_qa_lab/events.py` |
| Database | Persist events, unique source identities, cursors, and ETags | `src/mining_qa_lab/database.py` |
| Engine/API | Poll sources and approve exact PR heads/manual runs | `src/mining_qa_lab/engine.py`, `src/mining_qa_lab/web.py` |

## Interfaces and contracts

### CLI

- Polling runs under the orchestrator service; manual controls use the API/CLI
  and still create normal durable events.

### Configuration

- Repository policy defines event source, push branches, PR base branches,
  trusted contributors, and gate trigger enablement. Gates add change filters
  and schedules.

### Environment

- GitHub/QA tokens are read from configured environment references and never
  placed into event payloads.

### Python API

- `EventCollector`, `GithubClient`, `QaStatusFeedClient`, `cron_matches`, and
  `paths_match` define collection behavior.

### HTTP or external protocols

- GitHub REST uses ETags where available. QA deliveries use an ordered cursor.
  Operator PR approval requires PR number, gate, and expected 40-hex head SHA.

### Files, artifacts, payloads, and persistent state

- SQLite stores normalized trigger type, repository, exact commit, branch/PR,
  changed paths, payload, source identity, cursor, and planning state.

## Contract constraints

### Required invariants

- Manual requests bind a compatible repository/gate and persist the requested
  device types plus source-resolution provenance. With no commit/branch, the
  controller resolves configured `main`, then `master`, to a full commit SHA.
- An explicitly selected branch must be configured for that repository; an
  explicitly supplied commit remains the exact execution identity.

- Source identities are unique and replay-safe.
- Initial branch polling establishes a cursor without backfilling old work.
- Trusted PR automation is restricted by configured contributor/base policy.
- Untrusted approval re-fetches the PR and rejects any head-SHA mismatch.
- Schedule identities prevent duplicate events for the same occurrence.

### Forbidden behavior

- Do not run an untrusted or changed PR head under an earlier approval.
- Do not infer authorization from branch names, titles, or client payload alone.
- Do not advance past malformed deliveries without an explicit safe policy.

## Data and state

Source cursors/ETags track observation; durable events track accepted facts.
Planning state is separate so collection retries do not duplicate gate runs.

## Control and data flow

1. Read cursor and poll source with bounded requests.
2. Validate source facts and trust policy.
3. Persist normalized idempotent events.
4. Update cursor and expose unplanned events to the planner.

## Failure and recovery

Network/malformed-source failures preserve the prior cursor and are retried on a
later poll. Exact approval failure creates no event.

## Compatibility and migration

New event sources must map into the same normalized exact-commit contract and
define cursor, replay, authentication, and first-poll behavior.
Remote rerun requests are intentionally a separate leased queue: they requeue a
known exact run and do not create or advance source events/cursors.

## Resource and operational constraints

API pages, changed-path lists, polling intervals, response size, and timeouts
are bounded. ETags/cursors avoid unnecessary full-history polling.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Gate planning and supersession](../gate-planning-and-supersession/SPEC.md) | Consumes accepted unplanned events. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Stores cursors, idempotency keys, and event state. |
| [Operator API and UI](../operator-api-and-ui/SPEC.md) | Exposes exact-head approval and manual triggers. |
| [Artifact resolution and deployment](../artifact-resolution-and-deployment/SPEC.md) | Uses the event's exact commit as artifact identity. |

## Verification approach

Unit-test first-poll behavior, ETags/cursors, replay, branch/path filters,
trusted policy, exact-head approval race, schedules, and malformed responses.
