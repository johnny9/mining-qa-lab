# Firmware lifecycle — risks and scope

## Scope

### In

- Runner-side local artifact validation, OTA/USB execution, ordering, evidence,
  and post-reboot verification.

### Out

- Artifact compilation and CI trust resolution.
- Automatic rollback after each test.

## Assumptions

- Configured artifacts are appropriate for the exact target and recovery
  artifacts are retained by the operator.
- Device version/identity endpoints return after a successful reboot.

## Open questions

- A future explicit restore-firmware phase would need separate acceptance and
  must not be conflated with mutable cleanup.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Wrong artifact role | Boot/UI failure | Preflight and version/HIL | Reject role; recover with known-good images |
| Interrupted OTA | Device unavailable/unknown state | Timeout and API polling | Do not retry blindly; operator recovery |
| Version endpoint lies/stale | Wrong code tested | Reboot/identity/version checks | Add target-specific health evidence |
| USB path wrong | Wrong device flash | Unique path/identity preflight | Refuse ambiguity |

## Security, privacy, and safety

- Firmware flashing is destructive hardware mutation and requires explicit
  authorization, exact target identity, and recovery planning.

## Performance and resource risks

- Upload pacing too fast can overwhelm embedded HTTP; too slow can exceed
  service timeouts. Bounds need target evidence.

## Rollout and rollback

- Roll out one hardware profile/method at a time. Retain manufacturer/factory,
  application OTA, and filesystem/web OTA artifacts with their roles clearly
  labeled for recovery.
