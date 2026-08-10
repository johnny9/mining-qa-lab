# Firmware lifecycle — intent

## Problem

Tests must exercise an explicit firmware target, but web/application/factory
artifacts have different roles and a failed upload or wrong board can strand
hardware. Reflashing after every test is also slow and risky.

## Why it matters

The test result is meaningful only if the target version is verified. Artifact
role confusion or an unbounded/retried upload can make a software regression
look like hardware failure and complicate recovery.

## Stakeholders

- **Firmware developer** — needs evidence tied to the intended target version.
- **Lab operator** — needs bounded upgrade and preserved recovery paths.
- **Device adapter** — owns native artifact order and reboot verification.
- **Orchestrator deployment** — may install an exact CI artifact before the
  runner, after which the runner can verify rather than duplicate deployment.

## Desired outcome

Upgrades are opt-in, use only configured local artifacts and methods, perform
one bounded write per artifact in device-specific order, and verify online
identity/version before the test baseline is captured.

## Primary flow

1. Read current firmware identity and explicit upgrade configuration.
2. Skip if disabled or already at the expected version; otherwise validate
   artifact roles and apply OTA or USB procedure.
3. Wait for the same device identity and expected version, then capture mutable
   test baseline.

## Alternate and failure flows

- Missing/invalid artifacts or unsupported method fail before upload.
- Interrupted upload is not blindly retried.
- Version mismatch or reboot timeout fails setup and still closes interfaces.

## Non-goals

- Automatic per-test firmware rollback.
- Building firmware.
- Treating factory/merged images as application OTA.
