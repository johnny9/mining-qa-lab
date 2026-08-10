# Device capability contract — risks and scope

## Scope

### In

- Portable adapter lifecycle, capability, state, telemetry, factory, and test
  selection contracts.

### Out

- ASIC-internal driver architecture and pool-specific application behavior.

## Assumptions

- Native device APIs expose enough state to implement portable meanings.
- A configured adapter can establish identity before its first write.

## Open questions

- Multi-device tests may eventually require a setup-level abstraction rather
  than one `MiningDevice` per `MinerTestCase`.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Capability over-advertised | Test uses unsupported operation | Adapter/unit failure | Derive set from configured interfaces and implementation |
| Model branch enters generic test | Coverage fragments | Review/spec audit | Add a capability or device-only test |
| Wrong identity accepted | Mutation hits wrong hardware | Identity unit/HIL check | Fail before snapshot/write |
| Native state misnormalized | False health result | State fixture tests | Include positive and negative native examples |

## Security, privacy, and safety

- Adapter boundaries are safety boundaries because they convert generic intent
  into native hardware writes.

## Performance and resource risks

- An adapter monitor that blocks or emits unbounded state can starve tests or
  exhaust memory; transport and telemetry slices define limits.

## Rollout and rollback

- Add adapters behind a new type name. Keep existing types unchanged until
  generic tests, fake-device cleanup, and authorized target validation pass.
