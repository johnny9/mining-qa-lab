# Gate planning and supersession — risks

## Scope

### In

- Event eligibility, matrix creation, immutable policy, and supersession.

### Out

- Worker scheduling fairness and device cleanup.

## Assumptions

- Configuration references are valid and events are already authorized.

## Open questions

- Should future gates express richer quorum policies than the current required
  policy without obscuring parent status?

## Failure modes

- Duplicate planner passes create duplicate physical work.
- Change filters omit a required qualification gate.
- A config edit retroactively changes a queued run.
- Supersession cancels work already touching hardware.

## Security, privacy, and safety

Planning must retain exact source identity and never widen an event's approved
gate or commit scope.

## Performance and resource risks

Misconfigured large matrices can exhaust the queue; validation and operator
review should bound setup/module cardinality.

## Rollout and rollback

Roll out new planning policy on a non-required/manual gate first. Roll back by
restoring the prior config for new runs; historical snapshots remain unchanged.
