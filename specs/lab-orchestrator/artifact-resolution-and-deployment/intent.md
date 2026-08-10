# Artifact resolution and deployment — intent

## Problem

Qualifying the wrong build or flashing an incompatible artifact invalidates the
gate and may render lab hardware unavailable.

## Why it matters

Firmware deployment is the highest-risk bridge from source event to physical
device. Exact provenance, compatibility checks, and bounded recovery are required.

## Stakeholders

- Firmware maintainers expecting exact-commit qualification.
- Lab operators responsible for recoverable devices.
- Executors needing one stable deployed state across modules.

## Desired outcome

The orchestrator waits for one successful configured workflow at the gate SHA,
extracts/verifies the named firmware, checks target board identity, applies OTA,
verifies reboot, and records a reusable deployment marker.

## Primary flow

Resolve workflow by exact head SHA, locate unexpired named artifact, download
with bounded authorization, safely extract the configured member, verify digest,
check device board, OTA, wait for expected identity, and atomically mark success.

## Alternate and failure flows

- Failed/absent workflow times out without flashing.
- Archive/digest/board mismatch fails closed.
- Existing matching marker skips duplicate deployment for later assignments.

## Non-goals

- Building firmware locally.
- Guessing board compatibility from filenames alone.
- Automatic serial recovery after failed OTA.
