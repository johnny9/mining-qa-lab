# Parent gate publication — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Gate publisher | Build/post parent payload and attach child result IDs | `src/mining_qa_lab/qa_status.py` |
| Engine | Publish lifecycle updates and compute terminal aggregate status | `src/mining_qa_lab/engine.py` |
| Database | Persist parent external ID/URL and assignment child links | `src/mining_qa_lab/database.py` |
| External runner publisher | Independently publish each detailed child result | [`mining-qa-testcode` publisher](https://github.com/johnny9/mining-qa-testcode/blob/main/src/miner_testcode/publishers.py) |

## Interfaces and contracts

### CLI

- Publication follows normal service/manual gate execution; no operator command
  is required to copy child artifacts into a parent.

### Configuration

- `qa_status` defines enablement, base URL, token environment, and timeout;
  gate defines name/description and required policy.

### Environment

- Mining QA token is read from the configured environment reference and never
  serialized into parent/request data.

### Python API

- `GatePublisher.publish_run(...)` upserts/creates parent state;
  `link_result(...)` associates an existing child result with an assignment.

### HTTP or external protocols

- Parent POST uses stable `external_run_id`; child-link POST supplies parent ID,
  result ID, assignment/platform/setup/module, and required flag.

### Files, artifacts, payloads, and persistent state

- Parent payload contains gate/repository/commit/branch/PR/trigger/status/digest,
  timestamps/platforms/summary, request provenance, and assignment summaries.
  It contains no detailed artifact files.

## Contract constraints

### Required invariants

- Local durable assignment state is aggregated deterministically: queued/running,
  skipped/cancelled/error, then required policy for pass/fail.
- Parent request provenance distinguishes requester and authorization source.
- Manual request provenance includes selected project, device types, and source
  resolution alongside requester and authorization source.
- Parent external identity is stable for the local gate run.
- The stored public parent UUID and stable local external ID are both required
  when validating a remotely requested rerun.
- Child result ID/URL comes from the runner result pointer and is linked to the
  correct assignment.

### Forbidden behavior

- Do not upload child artifacts or duplicate detailed child records from parent.
- Do not accept the local archive as a substitute for a Mining QA child identity
  when QA publication is enabled.
- Do not claim passed while any required assignment is running/error/failed.
- Do not let publication failure rewrite the local test/gate outcome.
- Do not expose tokens or private lab coordinates in the payload.

## Data and state

Local gate run is authoritative execution state. Stored QA parent ID/URL and
assignment child ID/URL are correlation fields for repeat publication/linking.

## Control and data flow

1. Publish parent when run transitions to running.
2. Runner publishes child; executor records its ID/URL and links when parent exists.
3. After all assignments terminal, compute policy result and update parent.
4. Re-link known children idempotently on later parent publication.

## Failure and recovery

Publish/link errors are bounded and logged. Durable IDs allow later updates;
operators can diagnose missing links and inspect the private archive without
losing local results. The archive does not turn publication failure into success.

## Compatibility and migration

Parent payload and link endpoints are external contracts. Add fields compatibly
and coordinate status/required-policy changes with Mining QA consumers.

## Resource and operational constraints

Payload/assignment count, retries, request timeouts, and error bodies are bounded.
Detailed evidence remains in children to keep parent compact.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Gate planning and supersession](../gate-planning-and-supersession/SPEC.md) | Supplies matrix, digest, trigger, and required policy. |
| [Assignment execution](../assignment-execution/SPEC.md) | Supplies durable status and child ID/URL. |
| [Result model and publishing](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/result-model-and-publishing/SPEC.md) | Runner owns detailed child publication. |
| [Artifacts, privacy, and provenance](https://github.com/johnny9/mining-qa-testcode/blob/main/specs/test-runner/artifacts-privacy-and-provenance/SPEC.md) | Detailed evidence stays sanitized in child records. |
| [Central coordination agent](../central-coordination-agent/SPEC.md) | Central mode publishes one per-Lab completion to the Status-owned global gate instead of creating a local parent. |

## Verification approach

Unit-test every aggregate policy/status, payload provenance, stable external ID,
child linking/idempotency, disabled mode, timeout/error, and absence of artifacts.
