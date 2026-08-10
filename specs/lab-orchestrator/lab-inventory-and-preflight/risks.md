# Lab inventory and preflight — risks

## Scope

### In

- Inventory semantics and observational probe/preflight surfaces.

### Out

- Test execution, deployment, and automated physical repair.

## Assumptions

- Logical IDs are stable and operators keep physical wiring/config aligned.

## Open questions

- Which observed identities should become mandatory as more board types join?

## Failure modes

- Device address resolves to the wrong board.
- Serial symlink changes beneath a setup.
- Probe success becomes stale before execution.
- Photo source leaks unrelated host content.

## Security, privacy, and safety

Treat coordinates/photos as restricted operator data. Preflight is read-only
and must not be used as an unauthenticated network scanning primitive.

## Performance and resource risks

Slow SSH/API/camera endpoints can tie up requests; parallelism, bytes, and
timeouts must remain bounded.

## Rollout and rollback

Add inventory/probe fields optionally, observe reports, then make them required.
Rollback disables a probe without removing stable logical inventory.
