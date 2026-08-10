# Assignment execution — risks

## Scope

### In

- Lease-to-worker execution, environment, command, logs, timeout, and pointer.

### Out

- Test implementation and parent publication payload.

## Assumptions

- Runner executable/profile exists on the chosen host and honors its contracts.
- Remote job path is readable through the configured SSH identity.

## Open questions

- When should remote execution move from command SSH to a dedicated worker protocol?

## Failure modes

- Wrong profile/device name targets unintended equipment.
- Quoting or environment encoding changes command meaning.
- Runner cleans up but pointer retrieval fails, orphaning a child link.
- Process interruption leaves uncertain physical state despite lease recovery.

## Security, privacy, and safety

Minimize environment/SSH authority, sanitize logs, and bind execution to exact
approved commit and setup. Never treat lease release as hardware cleanup proof.

## Performance and resource risks

Worker output, SSH latency, stuck processes, and long HIL can consume resources;
enforce timeout/output/storage and configured concurrency bounds.

## Rollout and rollback

Exercise command changes on a manual non-required gate. Roll back the executor
while retaining job directories and durable error records for diagnosis.
