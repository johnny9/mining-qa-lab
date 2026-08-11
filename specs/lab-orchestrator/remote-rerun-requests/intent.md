# Remote rerun requests — intent

## Problem

Allowed Mining QA Status users can inspect a failed test or gate, but cannot ask
the private lab to rerun it without switching to a separate operator surface.
A public request must not become direct authority over devices or allow two lab
agents to execute the same work.

## Why it matters

Reruns are common during review and diagnosis. Making the request durable and
auditable shortens that loop while preserving the lab's final scheduling and
safety authority.

## Stakeholders

- Authenticated, allowlisted Mining QA Status users.
- Lab operators and redundant lab agents.
- Reviewers consuming parent and child evidence.

## Desired outcome

A signed-in user can request an entire terminal gate or one linked test again.
Mining QA Status records intent; one eligible lab agent leases it, validates the
exact public/private identity, and atomically requeues only the requested local
assignments.

## Primary flow

The browser submits a bounded request for a terminal gate snapshot. Status
deduplicates it and exposes it only to a scoped lab-agent token. A lab poll
claims one matching repository/gate request, checks the public parent ID, local
run ID, repository, gate, commit, and assignments, persists the remote request
ID, requeues the target, and resolves the claim as accepted.

## Alternate and failure flows

- A duplicate click returns the active request rather than creating more work.
- An expired claim can be leased by another agent.
- A stale, unknown, active, or mismatched local run is rejected without mutation.
- If remote resolution fails after local commit, redelivery is accepted
  idempotently without requeueing the assignments again.

## Non-goals

- Sending device addresses, credentials, setup topology, or commands to Status.
- Interrupting running hardware work.
- Selecting a different firmware revision or gate definition from a result page.
- Treating request acceptance as proof that a hardware test passed or finished.
