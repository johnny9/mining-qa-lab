# {{FEATURE_NAME}} — acceptance

Each criterion must be independently verifiable. Check an item only after
recording current evidence.

## Functional behavior

- [ ] **{{SPEC_ID}}-AC-01:** Given {{PRECONDITION}}, when
  {{ACTION_OR_EVENT}}, then {{OBSERVABLE_RESULT}}.
- [ ] **{{SPEC_ID}}-AC-02:** Invalid or unsupported input produces
  {{DEFINED_FAILURE_BEHAVIOR}}.

## Interfaces and compatibility

- [ ] **{{SPEC_ID}}-AC-03:** {{PUBLIC_API_PROTOCOL_FILE_FORMAT_CLI_OR_HARDWARE_INTERFACE}}
  remains compatible with {{SUPPORTED_CONSUMERS_OR_VERSIONS}}.
- [ ] **{{SPEC_ID}}-AC-04:** Any intentional incompatibility has an explicit
  migration or rollout path.

## Quality attributes

- [ ] **{{SPEC_ID}}-AC-05:** Applicable security, privacy, hardware safety,
  authorization, failure, and recovery requirements are verified.
- [ ] **{{SPEC_ID}}-AC-06:** Applicable performance, timing, memory, storage,
  power, image-size, capacity, or throughput requirements are met.

## Verification evidence

- `{{TEST_COMMAND_OR_CASE}}` — {{RESULT_AND_DATE}}
- `{{ANALYSIS_SIMULATION_MEASUREMENT_DEPLOYMENT_OR_HIL_CHECK}}` —
  {{RESULT_AND_DATE}}

## Acceptance rule

Work on this feature is acceptable only when all criteria affected by the
change have current evidence, related specs are reconciled, and unverified
criteria or environment limitations are reported explicitly.
