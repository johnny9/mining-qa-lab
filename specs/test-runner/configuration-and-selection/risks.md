# Configuration and selection — risks and scope

## Scope

### In

- Runner TOML, exact environment resolution, device/pattern selection, PR
  opt-in, and publisher selection.

### Out

- Orchestrator YAML and event trust.
- Live device discovery or hardware compatibility probing.

## Assumptions

- Local ignored profiles are controlled by the lab operator.
- The environment supplying secrets is trusted at process launch.

## Open questions

- No schema version currently exists for runner TOML; incompatible future
  changes need an explicit migration decision.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Wrong device selected | Unintended HIL target | Explicit requested-name validation and identity check | Use stable private names and adapter identity checks |
| Missing secret | Test cannot authenticate | `ConfigError` before run | Supply named environment variable without editing profile |
| Pattern matches nothing | False empty success | Suite loader count is zero | Fail configuration |
| Validation case runs broadly | Unsafe or misleading coverage | PR-selection unit tests | Default to explicit skips |

## Security, privacy, and safety

- TOML may name environment variables but must not contain committed secrets or
  private production coordinates.
- Selection is not a substitute for adapter identity verification.

## Performance and resource risks

- Unbounded discovery trees could increase startup cost; profiles should point
  to the intended E2E directory and pattern.

## Rollout and rollback

- Additive options should default safely. Breaking selection behavior requires
  profile/example migration and a changelog entry.
