# Remote rerun requests — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Mining QA Status UI/API | Authenticate requester and create bounded rerun intent | [`mining-qa-status` rerun control and API](https://github.com/johnny9/mining-qa-status/tree/main/src) |
| Status database | Deduplicate, lease, audit, and resolve requests | [`mining-qa-status` migrations](https://github.com/johnny9/mining-qa-status/tree/main/supabase/migrations) |
| Lab rerun client | Claim and resolve one matching request with bounded HTTP | `src/mining_qa_lab/reruns.py` |
| Lab database | Validate identity and atomically apply once | `src/mining_qa_lab/database.py` |
| Engine | Poll opt-in queue before normal planning | `src/mining_qa_lab/engine.py` |

## Interfaces and contracts

### CLI

No new command is required. Normal `poll-once` and service polling consume at
most one request when opt-in is enabled.

### Configuration

`qa_status.reruns_enabled` defaults to `false`. It uses the existing Status base
URL and token environment only after an operator issues a lab-agent token.

### Environment

The existing configured token environment contains the replacement scoped lab
token. Token values never enter SQLite, request payloads, or logs.

### Python API

`QaStatusRerunClient.claim/resolve`, `OrchestratorEngine.poll_reruns`, and
`OrchestratorDatabase.apply_remote_rerun` form the internal boundary.

### HTTP or external protocols

- Authenticated browser: `POST /api/v1/gates/runs/{id}/rerun` with mode `all`
  or `assignments` and a bounded assignment ID list.
- Lab agent: `POST /api/v1/lab/rerun-requests/claim` with configured public
  repository/gate targets.
- Lab agent: `POST /api/v1/lab/rerun-requests/{id}/resolve` with claim token,
  `accepted` or `rejected`, and optional bounded public detail.

### Files, artifacts, payloads, and persistent state

Status stores request audit/lease state. SQLite stores each applied remote
request ID and its local run/selection. Existing attempt-numbered artifacts are
not deleted or overwritten.

## Contract constraints

### Required invariants

- Only active browser profiles request work; bearer publishers cannot impersonate
  a user click.
- Only a super-admin bearer token with `gates:reruns:consume` can claim/resolve.
- A claim is exclusive, short-lived, opaque, and scoped to the token owner plus
  explicitly configured repository/gate targets.
- The public parent UUID equals local `qa_result_id`; public `external_run_id`
  equals local run ID; repository, gate, commit, and assignment IDs all match.
- Running/queued targets are never interrupted or reset.
- Local request recording and assignment requeueing share one transaction.

### Forbidden behavior

- Status must not receive device credentials, addresses, USB paths, setup IDs,
  runner profiles, shell commands, or arbitrary test arguments.
- A request must not create a new source revision or bypass gate configuration.
- Claim or resolution failure must not be interpreted as a completed test.

## Data and state

Status requests move `queued` → `claimed` → `accepted` or `rejected`. A lease
expiry returns claimability without losing attempts. Local terminal assignments
move to `queued`; their attempt counter and attempt-specific archive remain.

## Control and data flow

1. Status validates the current terminal parent snapshot and inserts/deduplicates.
2. Lab submits only configured public repository/gate targets and claims one row.
3. Lab performs exact local identity/state validation.
4. SQLite atomically records request ID and requeues selected assignments.
5. Lab resolves the Status lease; normal tick/execution republishes the parent.

## Failure and recovery

Before local commit, reject permanent mismatches or leave transient HTTP failure
for later polling. After local commit, repeated claims find the stored request ID
and resolve accepted without applying the transition twice.

## Compatibility and migration

Deploy the Status migration/API first, issue a replacement lab-agent token, then
deploy the lab with `reruns_enabled: false`. Enable polling only after a dry
claim against an empty queue. Rollback disables polling; queued Status requests
remain durable and no local state is down-converted.

## Resource and operational constraints

One request is claimed per controller poll. Target and assignment lists,
responses, resolution detail, HTTP timeout, and claim lease are bounded; no
network operation runs inside a SQLite transaction.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Event ingestion and trust](../event-ingestion-and-trust/SPEC.md) | Shares bounded authenticated external input but reruns existing exact work instead of creating source events. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Supplies atomic idempotency and preserves assignment attempts/evidence. |
| [Parent gate publication](../parent-gate-publication/SPEC.md) | Supplies the exact public/local correlation and republishes rerun state. |
| [Operator API and UI](../operator-api-and-ui/SPEC.md) | Remains the private operator control and diagnosis surface. |

## Verification approach

Use schema/route contract tests in Status and fake-client plus SQLite transaction
tests in the lab. Exercise lease replay and resolution failure without hardware;
reserve one explicit end-to-end request for staged rollout.
