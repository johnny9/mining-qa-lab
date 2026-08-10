# Lab inventory and preflight — intent

## Problem

Hardware tests depend on the right host, device model, API address, serial
adapter, profile, optional camera, and deployment compatibility. Configuration
validity alone cannot prove those resources are presently reachable or correct.

## Why it matters

Preflight reduces unsafe deployment, misleading test failures, and time spent on
disconnected or misidentified equipment.

## Stakeholders

- Lab operators maintaining physical setups.
- Executors/deployers consuming inventory.
- Developers diagnosing environmental failures.

## Desired outcome

Inventory describes stable logical resources, while bounded read-only probes
report current reachability and compatibility before a run.

## Primary flow

Resolve a setup to host/devices/profile, probe transport and device APIs, inspect
configured USB identity, optionally capture a bounded photo, then return a
structured pass/fail preflight report without mutating devices.

## Alternate and failure flows

- Disabled/missing devices fail preflight.
- Unreachable optional photo source is reported separately from required checks.
- SSH/local host probing uses the configured transport boundary.

## Non-goals

- Automatically repairing wiring or flashing firmware.
- Publishing private addresses/serial paths externally.
- Replacing runner-level capability detection after acquisition.
