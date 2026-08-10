# Parent gate publication — risks

## Scope

### In

- Aggregate status, parent payload, request provenance, and child linking.

### Out

- Detailed child evidence and external retention policy.

## Assumptions

- Mining QA upserts by stable external identity and preserves result links.

## Open questions

- Should optional assignments be represented individually when richer quorum
  policies are introduced?

## Failure modes

- Incorrect required-policy aggregation reports false pass/fail.
- Repeated requests create duplicate parents/links.
- Child ID attaches to the wrong assignment.
- Remote state lags local state after failure.

## Security, privacy, and safety

Parent payload is metadata only; retain no credentials, private coordinates, or
copied artifacts. Authorization source must be factual, not inferred loosely.

## Performance and resource risks

Large matrices can grow payloads and link calls; keep matrix cardinality and
request/retry behavior bounded.

## Rollout and rollback

Validate new fields against staging/disabled optional publication first.
Rollback disables publishing while local state and child records remain usable.
