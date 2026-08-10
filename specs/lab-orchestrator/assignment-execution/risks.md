# Assignment execution — risks

## Scope

### In

- Lease-to-worker execution, environment, command, logs, timeout, and pointer.

### Out

- Test implementation and parent publication payload.

## Assumptions

- A configured runner executable/profile exists on the chosen host, or enabled
  managed-testcode preparation can create it, and it honors its contracts.
- Remote job path is readable through the configured SSH identity.

## Open questions

- When should remote execution move from command SSH to a dedicated worker protocol?

## Failure modes

- A compromised worker supplies traversal, symlink, oversized, or hash-mismatched
  manifest entries.
- Retained logs exhaust controller disk without external capacity/retention
  operations.

- Wrong profile/device name targets unintended equipment.
- Worker testcode preparation fails before deployment or hardware construction.
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
