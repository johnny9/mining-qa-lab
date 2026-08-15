# Mining QA lab coordination contract v2

This document defines the private HTTP boundary between `mining-qa-status` and
`mining-qa-lab` for distributed advisory QA. The coordinated copy in the Lab
repository must remain byte-for-byte identical. Status owns the server and
global evidence; Lab owns local authorization, private bindings, hardware
safety, execution, and cleanup.

Version 2 is additive. It does not change the existing result, gate, or rerun
APIs and remains disabled until both sides have compatible readers.

## Common wire rules

- All requests and responses use UTF-8 JSON with
  `Content-Type: application/json`.
- Registration, heartbeat, subscription, work, claim, and renewal bodies are
  limited to 64 KiB. Completion bodies are limited to 256 KiB.
- Timestamps are RFC 3339 UTC strings with a trailing `Z`. Durations are
  positive integer seconds.
- Opaque IDs are 1–128 ASCII characters matching
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. They convey no hierarchy and must not be
  parsed for meaning.
- A definition digest is exactly 64 lowercase hexadecimal characters and is
  the SHA-256 of the canonical portable definition described below.
- Repository names use `owner/name` and are at most 200 characters. Commit
  SHAs are exactly 40 lowercase hexadecimal characters in version 2.
- Human labels, reason codes, and URLs are bounded by the endpoint schema. No
  response body, list, cursor page, or error detail is unbounded.
- Unknown object fields are rejected. Adding a field requires a coordinated
  reader-first update to both copies of this contract.
- Agent routes require a scoped bearer credential. Bootstrap registration
  additionally requires a one-use operator-issued bootstrap credential.
- Secrets, bearer values, bootstrap values, and claim tokens are never logged,
  published, or returned by public Status APIs.

Every mutating request carries an `idempotency_key`, an opaque ID unique within
its route and lab. Repeating the same key with the same canonical body returns
the original response. Reusing it with a different body returns `409
idempotency_conflict`.

## Portable definition and digest

Status freezes this object when it creates a gate run:

```json
{
  "project": {
    "id": "firmware",
    "repository": "owner/firmware"
  },
  "gate": {
    "id": "firmware-advisory",
    "revision_id": "gate-rev-0001"
  },
  "suite": {
    "id": "mock-device-smoke",
    "revision_id": "suite-rev-0001",
    "requirements": [
      {
        "requirement_id": "gamma-http-and-stratum",
        "platform_class": "gamma-600",
        "device_model": "Gamma 602",
        "capabilities": ["http", "stratum-v1"],
        "test_pattern": "test_integration_smoke.py"
      }
    ]
  },
  "trigger": {
    "id": "manual-local",
    "revision_id": "trigger-rev-0001",
    "type": "manual"
  }
}
```

Canonicalization recursively sorts object keys, preserves array order, encodes
JSON as UTF-8 without insignificant whitespace, and forbids floats, duplicate
keys, non-JSON values, and Unicode normalization changes. `definition_digest`
is the lowercase SHA-256 of those exact bytes. Source target, eligible labs,
deadlines, and private bindings are not part of this digest and are frozen in
their own records.

Each suite has 1–32 requirements. IDs and capabilities use the opaque-ID rule;
`platform_class` and `device_model` are non-identifying public classifications
of at most 80 characters; `test_pattern` is 1–200 characters and cannot contain
path traversal, shell syntax, control characters, or whitespace-delimited
extra arguments. The definition describes intent, never a shell command,
hostname, credential, local path, setup, profile, or physical device.

## Source target

Every offer contains one immutable source target:

```json
{
  "repository": "owner/firmware",
  "commit_sha": "0123456789abcdef0123456789abcdef01234567",
  "ref_name": "main",
  "pr_number": null
}
```

`ref_name` is 0–255 characters. `pr_number` is `null` or a positive integer no
greater than 2147483647. The commit is authoritative; the ref and PR are
provenance only.

## Registration

`POST /api/v2/labs/register`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "register-lab-east-0001",
  "lab_id": "lab-east",
  "public_lab_label": "East Lab",
  "agent_version": "0.1.0",
  "supported_coordination_versions": [2],
  "supported_orchestration_versions": [1, 2]
}
```

Response `201` for first registration or `200` for an idempotent replay:

```json
{
  "contract_version": 2,
  "lab_id": "lab-east",
  "registration_id": "registration-0001",
  "agent_token": "one-time-secret-value",
  "issued_at": "2026-08-14T12:00:00Z"
}
```

`public_lab_label` and `agent_version` are 1–80 printable characters. The token
is returned only on creation or explicit rotation, is stored hashed by Status,
and is never returned by later reads. Registration cannot change a lab ID or
silently reactivate a disabled lab.

## Heartbeat

`POST /api/v2/labs/{lab_id}/heartbeat`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "heartbeat-lab-east-0001",
  "agent_version": "0.1.0",
  "sent_at": "2026-08-14T12:00:10Z",
  "available_slots": 1,
  "capabilities": [
    {
      "platform_class": "gamma-600",
      "device_model": "Gamma 602",
      "features": ["http", "stratum-v1"],
      "aggregate_state": "available",
      "evidence_at": "2026-08-14T12:00:09Z"
    }
  ],
  "health_code": "ok"
}
```

There are at most 64 capability entries and 64 unique features per entry.
`available_slots` is 0–64 and remains private. `aggregate_state` is one of
`available`, `busy`, `offline`, `stale`, or `unknown`. `health_code` is one of
`ok`, `degraded`, `paused`, or `error`. Status derives public freshness from
server receipt time; the agent timestamp is diagnostic only.

Response `200`:

```json
{
  "contract_version": 2,
  "accepted_at": "2026-08-14T12:00:10Z",
  "next_heartbeat_seconds": 30,
  "registration_state": "active"
}
```

Heartbeats never contain device counts by class, device IDs, addresses,
hostnames, setup/profile names, paths, usernames, raw errors, or credentials.

## Subscriptions

`PUT /api/v2/labs/{lab_id}/subscriptions`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "subscriptions-lab-east-0001",
  "revision": 1,
  "gate_ids": ["firmware-advisory"]
}
```

`revision` is a monotonically increasing positive integer and there are at
most 128 unique gate IDs. A stale revision returns `409 stale_revision`; the
same revision and body is idempotent. Response `200` echoes the accepted
revision and server timestamp.

## Work offers

`GET /api/v2/labs/{lab_id}/work?after={cursor}&limit={limit}`

`cursor` is opaque and at most 256 characters. `limit` is 1–32 and defaults to
10. A missing cursor starts from the agent's durable acknowledged position; it
does not request historical work predating registration.

Response `200`:

```json
{
  "contract_version": 2,
  "cursor": "cursor-0002",
  "next_poll_seconds": 5,
  "offers": [
    {
      "central_gate_run_id": "global-run-0001",
      "lab_execution_id": "lab-execution-east-0001",
      "lab_id": "lab-east",
      "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78",
      "definition": {},
      "source": {},
      "offered_at": "2026-08-14T12:00:15Z",
      "deadline_at": "2026-08-14T12:05:15Z",
      "claim_ttl_seconds": 120,
      "max_claim_generations": 2
    }
  ]
}
```

The abbreviated `definition` and `source` values above have the exact shapes
defined earlier. Offers are at most 64 KiB each. `claim_ttl_seconds` is 30–900;
`max_claim_generations` is 1–5. Offer replay is expected and does not authorize
duplicate local work. The immutable uniqueness key is
`(central_gate_run_id, lab_id)` and maps to exactly one `lab_execution_id`.
The agent transactionally persists every validated offer and the returned
cursor before its next pull. If that transaction does not commit, it reuses the
previous `after` cursor and relies on bounded replay; reading an HTTP response
alone never advances durable delivery state.

## Claim

`POST /api/v2/executions/{lab_execution_id}/claim`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "claim-east-0001",
  "lab_id": "lab-east",
  "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78"
}
```

Response `200`:

```json
{
  "contract_version": 2,
  "claim_id": "claim-east-0001",
  "claim_generation": 1,
  "claim_token": "private-lease-capability",
  "lease_expires_at": "2026-08-14T12:02:15Z"
}
```

Only one active claim exists for an execution. `claim_token` is a private
capability bound to execution, lab, and generation; Status stores only its
hash. A competing claim returns `409 already_claimed`. Digest or lab mismatch
returns `409 offer_mismatch` before any lease is created.

## Renewal

`POST /api/v2/executions/{lab_execution_id}/renew`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "renew-east-0001",
  "claim_id": "claim-east-0001",
  "claim_generation": 1,
  "claim_token": "private-lease-capability"
}
```

Response `200` returns the same claim identity and a later
`lease_expires_at`. Renewal is accepted only for the current active generation,
before its expiry and before the gate-run deadline. An expired or replaced
claim returns `409 claim_expired`; it is never resurrected.

## Decline

`POST /api/v2/executions/{lab_execution_id}/decline`

An authenticated Lab may decline an offered execution before claim when a
portable requirement, deadline, or local policy cannot be accepted. It may
also decline its own active claim before local runner start. Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "decline-east-0001",
  "lab_id": "lab-east",
  "observed_definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78",
  "claim": null,
  "reason_code": "no_safe_binding"
}
```

`claim` is null while the execution is offered. While claimed, it is the exact
`claim_id`, `claim_generation`, and `claim_token` object used by completion.
`observed_definition_digest` is the bounded digest received by the agent; it
may differ from Status truth only when `reason_code` is
`definition_mismatch`. Allowed reasons are `no_safe_binding`,
`unsupported_requirement`, `local_policy_rejected`, `local_capacity_changed`,
`deadline_too_close`, `definition_mismatch`, and `invalid_offer`.

Response `200` returns `lab_execution_id`, `state: "declined"`, and
`accepted_at`. Status derives a sanitized public unavailable participant record
from its frozen definition and Lab identity; it does not publish the rejected
body or local diagnostic. Decline is terminal and starts no replacement claim.

## Completion

`POST /api/v2/executions/{lab_execution_id}/complete`

Request:

```json
{
  "contract_version": 2,
  "idempotency_key": "complete-east-0001",
  "claim": {
    "claim_id": "claim-east-0001",
    "claim_generation": 1,
    "claim_token": "private-lease-capability"
  },
  "private_correlation": {
    "central_gate_run_id": "global-run-0001",
    "lab_execution_id": "lab-execution-east-0001",
    "lab_id": "lab-east",
    "local_gate_run_id": "local-run-east-0001",
    "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78"
  },
  "published_completion": {
    "central_gate_run_id": "global-run-0001",
    "lab_execution_id": "lab-execution-east-0001",
    "lab_id": "lab-east",
    "public_lab_label": "East Lab",
    "platform_class": "gamma-600",
    "device_model": "Gamma 602",
    "project_id": "firmware",
    "gate_id": "firmware-advisory",
    "gate_revision_id": "gate-rev-0001",
    "suite_id": "mock-device-smoke",
    "suite_revision_id": "suite-rev-0001",
    "trigger_id": "manual-local",
    "trigger_revision_id": "trigger-rev-0001",
    "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78",
    "outcome": "passed",
    "started_at": "2026-08-14T12:00:20Z",
    "completed_at": "2026-08-14T12:01:20Z",
    "source": {},
    "testcode": {
      "repository": "johnny9/mining-qa-testcode",
      "ref": "main",
      "commit_sha": "89abcdef0123456789abcdef0123456789abcdef"
    },
    "children": [
      {
        "assignment_id": "assignment-east-0001",
        "attempt_id": "attempt-east-0001",
        "runner_run_id": "runner-east-0001",
        "status": "passed",
        "result_id": "result-east-0001",
        "result_url": "http://localhost:3000/results/result-east-0001"
      }
    ],
    "reason_code": null
  }
}
```

The abbreviated `source` has the exact source-target shape. `outcome` is one of
`passed`, `failed`, `error`, `skipped`, or `unavailable`. `reason_code` is
`null` for ordinary completed evidence or one bounded opaque ID for a sanitized
condition. There are at most 32 children. Child `status` uses the same concrete
outcomes except `unavailable`; URLs are HTTP(S), at most 2048 characters, and
must match the configured Status public origin. Child IDs and links are
immutable once accepted.

Status verifies all duplicated IDs, source, revisions, digest, public lab
identity, and claim generation against frozen server records. It stores
`private_correlation` and claim diagnostics only in protected records. It
stores `published_completion` as the complete public record after recursive
privacy validation; it never hides private fields inside that record.

Response `200`:

```json
{
  "contract_version": 2,
  "lab_execution_id": "lab-execution-east-0001",
  "state": "completed",
  "accepted_at": "2026-08-14T12:01:20Z"
}
```

Completion requires the current unexpired claim. A completion arriving after
expiry returns `409 claim_expired`, records a private bounded late-completion
event, and never overwrites accepted or terminal evidence. The lab retains its
local evidence for operator review.

## State machines

### Status lab execution

```text
offered -> claimed -> completed
                   -> declined
                   -> offered   (lease expired, retry budget and deadline remain)
                   -> expired   (lease expired and no retry remains)
offered -> declined            (portable/local policy rejection)
offered -> expired             (gate-run deadline reached)
```

- `offered`, `claimed`, `completed`, `declined`, and `expired` are persisted.
- Every claim generation is immutable. An active lease moves to `released` on
  accepted completion/decline or `expired` at its deadline.
- A replay cannot create a second execution, claim generation, or completion.
- Terminal evidence is immutable. Retry creates a new claim generation, never
  a new `lab_execution_id` for the same frozen participant.

### Lab local execution

```text
received -> binding -> queued -> running -> terminal
```

`terminal` carries `passed`, `failed`, `error`, `skipped`, or `unavailable`.
The lab persists the offer and central IDs before claiming, freezes the private
binding before queueing, and creates a distinct immutable attempt for each
runner invocation. Central expiry never cancels runner cleanup.

### Global gate run

```text
queued -> running -> complete
                  -> timed_out
```

The participant set is frozen when the run is created. Lifecycle, coverage,
and assessment are derived independently:

| Frozen evidence | Lifecycle | Coverage | Assessment |
|---|---|---|---|
| All terminal and all usable; all pass/skip | `complete` | `complete` | `clear` |
| All terminal and any usable fail/error | `complete` | `complete` | `concerns` |
| Any declined/expired/unavailable or contradictory evidence | `complete` or `timed_out` | `partial` or `unavailable` | `inconclusive` |
| No eligible participants | `complete` | `unavailable` | `inconclusive` |

Skipped child checks are neutral and excluded from pass/fail totals. A whole
lab execution with only skipped evidence is usable only when the suite policy
explicitly permits it; otherwise it is inconclusive.

## Error response

Non-2xx responses use:

```json
{
  "error": {
    "code": "claim_expired",
    "message": "bounded non-sensitive explanation",
    "request_id": "request-0001",
    "retryable": false
  }
}
```

`message` is at most 500 characters and contains no request body, token, local
path, device identity, or raw upstream error. Expected codes include
`invalid_request` (400), `unauthorized` (401), `forbidden` (403), `not_found`
(404), `already_claimed`, `claim_expired`, `offer_mismatch`,
`stale_revision`, and `idempotency_conflict` (409), `payload_too_large` (413),
`rate_limited` (429), and `internal_error` (500). Only safe reads, heartbeat,
renewal, and byte-identical idempotent mutations may be retried automatically.

## Privacy boundary

Registration and private coordination may contain only the allowlisted fields
above. No request may contain a physical device ID or alias, serial/USB/MAC/IP
identity, hostname, local URL, payout address, pool identity, credential,
setup/profile ID, command, local path, raw log, or resolved environment value.

Published completion data is safe as stored and safe to return unchanged. The
only public hardware classification is platform/model class. Assignment,
attempt, runner, gate-run, and execution IDs are random per-run opaque values
and are never derived from a device or private binding.

## Reader/writer rollout

1. Deploy Status schema and readers with v2 routes disabled.
2. Deploy Lab DTO readers and durable state with central mode disabled.
3. Enable simulated registrations and offers only.
4. Enable claim/renew/complete for deterministic local integration.
5. Enable a real lab only after separate authorization and accepted simulation
   evidence.

Rollback disables writers in reverse order. Historical records and additive
readers remain; rollback never rewrites terminal evidence or down-converts a v2
record.
