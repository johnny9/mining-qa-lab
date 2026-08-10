# Lifecycle and cleanup — intent

## Problem

Tests may restart miners, alter pool settings, pause mining, or install target
firmware. Assertions, setup errors, protocol failures, and interface outages
must not leave mutable device state changed or hide cleanup failure.

## Why it matters

An apparently successful regression that strands a miner on a test pool or
writes a privacy placeholder is operationally worse than an explicit failure.
Reliable cleanup is the precondition for repeatable shared-lab testing.

## Stakeholders

- **Lab operator** — needs the device returned to its captured mutable state.
- **Test author** — needs cleanup independent of the test assertion path.
- **Device adapter** — owns the exact native snapshot and restore behavior.
- **Result consumer** — needs cleanup failure represented as an error.

## Desired outcome

Every started case either restores a valid baseline and closes its interfaces,
or reports explicit cleanup errors with local evidence. Unsafe baselines fail
before a test mutation.

## Primary flow

1. Start and identify the device, then ensure configured target firmware.
2. Capture a valid mutable-state baseline and run the test body.
3. Restore state within a bounded timeout, collect device logs, and close all
   interfaces regardless of test outcome.

## Alternate and failure flows

- Missing capabilities skip before device lifecycle.
- Baseline values containing redaction markers fail before mutation.
- Restore, log collection, and close are attempted independently; multiple
  cleanup failures are reported together.

## Non-goals

- Automatically rolling firmware back after every test.
- Guessing write-only baseline passwords.
- Suppressing cleanup failure to preserve a passing assertion.
