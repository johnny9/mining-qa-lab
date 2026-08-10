# Testcode bootstrap — risks

## Scope

### In

- Latest-branch resolution, immutable gate pin, managed checkout/venv install,
  local/SSH execution, provenance verification, and failure containment.

### Out

- Updating/restarting the orchestrator service, arbitrary package sources,
  untrusted PR harness execution, and host image/package management.

## Assumptions

- Workers are Linux/POSIX hosts with Git, Python, venv, pip, HTTPS access, and
  enough disk space.
- The configured GitHub branch is the operator-approved source of current tests.
- Managed checkout and venv paths are dedicated to this feature.

## Open questions

- Should a future policy select signed releases/tags instead of a branch head?
- Should dependency locking or a built wheel replace editable installation once
  release automation exists?

## Failure modes

- Branch moves between resolution and fetch; exact-SHA fetch prevents substitution.
- Dependency/index outage prevents installation and blocks the assignment.
- Existing checkout names another repository or contains tracked modifications.
- Venv executable imports an older globally installed package instead of checkout.
- Gate marker is truncated, tampered with, or inconsistent with captured config.
- Old orchestrator cannot understand an incompatible latest runner pointer contract.

## Security, privacy, and safety

The configured branch can execute code with lab-host and device authority, so
repository write access is part of the lab trust boundary. Use public GitHub
HTTPS without embedded credentials, never forward the SSH agent, never log
capability URLs/tokens, and fail before device mutation on bootstrap mismatch.

## Performance and resource risks

Installing before every assignment adds network, CPU, and disk work and may
hold device leases longer. Exact gate pins and one checkout/venv limit drift and
storage; command timeouts and bounded diagnostics prevent indefinite blockage.

## Rollout and rollback

Enable on one manual non-required local setup, verify exact provenance and
cleanup, then enable SSH/gated use. Roll back by setting `testcode.enabled=false`
and restoring the previously configured `miner_test`; retain markers/logs for
diagnosis and do not delete operator files automatically.
