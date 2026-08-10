# Operator API and UI — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| FastAPI app | Security middleware, REST routes, lifespan, background loop | `src/mining_qa_lab/web.py` |
| UI renderer | Render overview, gates, lab, trigger, and advanced pages | `src/mining_qa_lab/ui.py` |
| CLI | Initialize/validate config, serve, poll once, and manual run | `src/mining_qa_lab/cli.py` |
| Engine/store/database | Execute authorized domain operations | `src/mining_qa_lab/engine.py`, `src/mining_qa_lab/config.py`, `src/mining_qa_lab/database.py` |

## Interfaces and contracts

### CLI

- `miner-orchestrator init-config`, `validate`, `serve`, `poll-once`, and
  `run GATE SHA [--branch] [--wait]` are supported operator commands.

### Configuration

- Controller defines bind/port, state directory, poll interval, `bearer` or
  `none` auth, token environment, allowed networks, and environment allowlist.

### Environment

- Bearer token comes from configured environment or a generated mode-0600 state
  file; the service logs its path, not its value.

### Python API

- `create_app(store, database, engine)` builds the service and OpenAPI contract;
  `render_page` produces presentation from server truth.

### HTTP or external protocols

- `/api/v1/health`; config JSON/YAML, validate/reload/revisions; CRUD for
  repositories/modules/gates/hosts/devices/setups; gate validation/manual run;
  PR list/exact-head approval; events/runs/assignments; confirmed retry of
  eligible terminal runs; per-run artifact list, UTF-8 view, and download;
  host/device/USB/photo/setup preflight. Mutations require authorization; config
  edits require ETag.

### Files, artifacts, payloads, and persistent state

- Generated token, uploaded device photos, config backups, and SQLite/jobs live
  below configured state/config roots with bounded names/content/permissions.

## Contract constraints

### Required invariants

- Allowed-network checks apply before route handling when configured.
- Every mutating route requires bearer authorization unless `auth_mode=none`;
  no-auth config is valid only with explicit allowed networks.
- Configuration mutations require `If-Match` and full validation.
- Exact PR approval verifies repository/gate relationship and expected full SHA.
- Manual gates validate the project/gate relationship and selected device types.
  A blank source resolves configured `main`, then `master`, to an exact SHA at
  submission; explicit commits remain exact identities.
- Artifact APIs serve only persisted archive records whose resolved paths remain
  below `state_dir/archive`; inline viewing is UTF-8 and limited to 1 MiB.
- Retry eligibility is derived on the server-rendered history view. The UI offers
  the action only for failed, errored, or cancelled runs, confirms the gate and
  exact commit, and delegates to the authenticated retry route. Passed
  assignments remain passed.
- List limits, request/photo bodies, probe output, subprocesses, and network
  calls are bounded.
- UI is a view/client of server domain state, not a second policy implementation.

### Forbidden behavior

- Do not expose the service unauthenticated to unrestricted networks.
- Do not return/log bearer token or embed it in rendered pages.
- Do not mutate configuration/database files directly through arbitrary paths.
- Do not call `/health` proof that background polling or hardware is healthy;
  it currently reports API/config/queue snapshot only.

## Data and state

Config store and database remain authoritative. API payloads are versioned views;
UI pages render selected current snapshot/history and issue explicit actions.

## Control and data flow

1. Lifespan recovers interrupted state and starts bounded poll/tick loop.
2. Middleware applies network policy; dependencies authorize mutations.
3. Routes validate inputs and delegate to store/engine/database; retry returns
   durable state after incomplete assignments are requeued.
4. Responses expose revisions or durable IDs; UI renders the same contracts.

## Failure and recovery

Invalid/stale requests fail without mutation. Background-loop exceptions are
logged and the loop continues; health must not overstate unmeasured loop status.

## Compatibility and migration

Keep `/api/v1` backward compatible or introduce a new API version. OpenAPI and
API tests are contract evidence; UI may evolve without changing domain semantics.

## Resource and operational constraints

Request body/list/photo/probe output, HTTP/subprocess timeouts, poll frequency,
and background execution are bounded. Service is intended for a restricted lab.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Supplies validated ETag-controlled mutations. |
| [Event ingestion and trust](../event-ingestion-and-trust/SPEC.md) | Supplies PR/manual actions and background polling. |
| [Lab inventory and preflight](../lab-inventory-and-preflight/SPEC.md) | Supplies lab resources and probe endpoints. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Supplies history, cancellation, retry, and startup recovery. |
| [Service deployment](../service-deployment/SPEC.md) | Uses health counts and bounded logs as separate operational signals during cutover and rollback. |

## Verification approach

Use ASGI tests for auth/network, ETags, schemas/routes, CRUD, exact approval,
history/actions, retry eligibility and authentication, probes/photos/preflight,
page separation, and OpenAPI visibility. Also cover manual source/device
selection and authenticated artifact isolation, view bounds, binary rejection,
and downloads.
