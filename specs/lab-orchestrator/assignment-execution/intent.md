# Assignment execution — intent

## Problem

Planned assignments must be translated into a safe runner invocation on the
correct host/setup without leaking the service environment or losing the link
to detailed child results.

## Why it matters

Execution is the orchestrator/runner seam. Ambiguity here can target the wrong
device, run the wrong module/revision, expose credentials, or orphan evidence.

## Stakeholders

- Lab operators observing jobs and logs.
- Test-runner maintainers evolving CLI/pointer contracts.
- Parent-gate publication consuming assignment status/links.

## Desired outcome

After exclusive leases and optional exact deployment, the orchestrator launches
one bounded `miner-test` process with the captured profile/module/device and
provenance, then durably records its normalized status and child pointer.

## Primary flow

Load the gate snapshot, acquire setup resources, create a unique job directory,
ensure deployment, construct a minimal environment/command, execute with timeout,
capture log and pointer, validate status/child identity, and finish the assignment.

## Alternate and failure flows

- Lease conflict leaves work queued.
- Disabled device, deployment error, timeout, malformed/missing pointer, SSH or
  process failure becomes assignment error with bounded detail.
- Runner failure remains a failed/error child outcome, not an executor crash.

## Non-goals

- Implementing tests or device cleanup inside the orchestrator.
- Forwarding the host service environment wholesale.
- Parsing worker logs as the authoritative result contract.
