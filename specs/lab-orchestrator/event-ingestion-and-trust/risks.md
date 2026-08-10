# Event ingestion and trust — risks

## Scope

### In

- Source polling, authorization, normalization, cursoring, and manual events.

### Out

- Gate matrices and worker execution.

## Assumptions

- External APIs return stable immutable commit identifiers.
- Operator identity/authentication is enforced by the control plane.

## Open questions

- Should future webhook ingestion share the same delivery ledger or use a
  separate signed-delivery boundary?

## Failure modes

- Cursor advances before an event is durable.
- Force-push makes a previously displayed PR head stale.
- Rate limits delay or page away eligible changes.
- Schedule timezone/clock behavior duplicates an occurrence.

## Security, privacy, and safety

Untrusted code is fail-closed: approval binds gate, PR, and full current SHA.
Remote payloads are untrusted input and bounded before parsing/storage.

## Performance and resource risks

Large histories and compare path sets consume API quota and storage; polling,
pagination, and stored payload size remain bounded.

## Rollout and rollback

Introduce new sources disabled and observe cursor behavior. Roll back by
disabling that source without deleting already accepted durable events.
