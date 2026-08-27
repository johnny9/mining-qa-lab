# Central coordination agent — intent

## Problem

Distributed gates need Labs to consume shared portable intent, but Status
cannot know or authorize private hosts, devices, credentials, profiles, leases,
or cleanup. Network replay, restart, and lease expiry must not duplicate or
interrupt hardware work.

## Why it matters

The Lab is the final safety boundary. A central scheduler can improve coverage
only if every offer still passes local trust, binding, preflight, leasing, and
runner cleanup and if private topology never leaves the Lab.

## Stakeholders

- Lab operators control enrollment, bindings, pause, recovery, and evidence.
- Status supplies authenticated portable definitions and accepts sanitized
  completion.
- Testcode consumes one immutable v2 invocation and owns device lifecycle.
- Reviewers rely on complete correlation without receiving local identity.

## Desired outcome

An explicit central-mode agent registers sanitized capability, pulls and
claims one valid offer exactly once, freezes one private binding, executes
through immutable attempts, renews while active, and submits an idempotent
sanitized completion. A binding explicitly selects either loopback simulation
or a locally authorized hardware runner; central input can never choose that
execution class, profile, executable, device, environment, or resource. Local
mode remains compatible and independently usable.

## Primary flow

1. Validate central configuration, bind one app-issued Lab token, heartbeat,
   replace subscriptions, and persist the pull cursor.
2. Validate and persist an offer, claim it, resolve exactly one private
   binding, acquire local resources, and create a v2 Testcode attempt.
3. Persist cleanup and child pointer, submit one completion through the outbox,
   and retain correlation/evidence across restart.

## Alternate and failure flows

- Invalid definition, deadline, source, capability, or binding is declined
  before runner/device access with a bounded sanitized reason.
- A hardware runner failure after launch is terminal and is not automatically
  retried; the operator must inspect cleanup/device state before new work.
- Central outage retries only safe/idempotent operations from a bounded outbox.
- Claim expiry during a run never interrupts cleanup; late completion becomes
  an operator-visible conflict while local evidence remains immutable.
- Service restart reopens durable state and cannot create a second local
  assignment for a replayed central execution.

## Non-goals

- Letting Status lease or command local hardware.
- Uploading private bindings, exact capacity, local logs, or cleanup internals.
- Automatically importing/deleting existing local definitions.
- Letting a portable definition choose private process arguments or environment.
