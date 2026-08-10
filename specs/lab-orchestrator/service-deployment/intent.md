# Service deployment — intent

## Problem

The orchestrator is a long-running process with durable queue state and access
to physical lab devices. A casual pull, package update, or restart can mix code
versions, interrupt cleanup, lose the rollback path, or confuse the service
environment with the separately managed test runner.

## Why it matters

Operators need repeatable service updates that can be explained, inspected,
and reversed. Device safety and truthful run state matter more than minimizing
a short planned outage.

## Stakeholders

- Lab operators installing and updating the service.
- Maintainers publishing orchestrator changes.
- Active assignments that must finish cleanup before a planned restart.
- Reviewers verifying exact deployed source and rollback readiness.

## Desired outcome

One systemd user service runs an exact prepared release. Configuration,
secrets, state, artifacts, and managed worker testcode live outside that
release. Updates prepare and validate a candidate before an idle cutover, and a
retained prior release provides a fast rollback.

## Primary flow

1. Resolve and record one exact source SHA, prepare its release and isolated
   service venv, and validate it without changing the running service.
2. Confirm the current service has no running assignment, stop it gracefully,
   atomically select the candidate, and start it.
3. Verify systemd state, bounded journal output, API health/config revision, and
   preserve the previous release until rollback is no longer needed.

## Alternate and failure flows

- Active work delays the update; it is not cancelled or interrupted implicitly.
- Candidate preparation or configuration validation fails before cutover.
- Failed startup/health verification selects the retained previous release and
  restarts it while durable state remains untouched.
- An uncertain interrupted assignment remains fail-closed and requires
  operator hardware inspection before retry.

## Non-goals

- Automatically patching the operating system, firewall, or USB permissions.
- Treating `/api/v1/health` as proof that polling, hardware, or a pool is healthy.
- Updating worker testcode and the orchestrator service as one environment.
- Performing firmware deployment or HIL as part of a service software update.
