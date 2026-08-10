# Testcode bootstrap — intent

## Problem

Long-lived lab hosts can retain an old `miner-test` installation even after the
test harness gains new tests, safety checks, device support, or publisher
contracts. Installing directly from a moving branch also makes a result
impossible to reproduce if the exact code is not retained.

## Why it matters

Firmware qualification should use the current supported harness without
silently running stale tests. At the same time, every assignment in one gate
must identify the exact harness commit that executed it.

## Stakeholders

- Lab operators maintaining local and SSH workers.
- Test-runner maintainers shipping new tests and safety behavior.
- Reviewers relying on exact testcode provenance in child results.
- The orchestrator aggregating multiple assignments into one gate.

## Desired outcome

When enabled, the orchestrator resolves the latest commit of one configured
GitHub branch once per gate and worker host, installs that exact checkout into a
dedicated virtual environment before every assignment, and launches only the
verified installed runner.

## Primary flow

Resolve the branch head, retain an immutable gate/host marker, verify or clone
the managed checkout, refuse tracked local modifications, fetch and detach at
the exact commit, create/update the isolated environment, install editable
testcode, verify its import path, and pass the expected repository/SHA to the
runner before firmware or test execution.

## Alternate and failure flows

- Disabled bootstrap preserves the configured existing `miner_test` behavior.
- A later assignment in the same gate reuses the pinned SHA even if the branch
  moves, but reinstalls/verifies it before execution.
- Resolution, checkout, environment, installation, or verification failure
  releases the assignment lease and prevents firmware deployment and tests.
- A runner that observes different repository/SHA metadata fails before
  constructing a device.

## Non-goals

- Updating or restarting the currently running orchestrator process.
- Installing unreviewed pull-request testcode or arbitrary package indexes.
- Destroying tracked changes in an operator-managed checkout.
- Making one gate mix testcode revisions merely because the branch moved.
