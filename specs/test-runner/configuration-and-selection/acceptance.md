# Configuration and selection — acceptance

## Functional behavior

- [x] **TR-CONFIG-AC-01:** Valid TOML resolves generic interfaces, environment
  values, devices, tests, and publishers into immutable configuration.
- [x] **TR-CONFIG-AC-02:** Duplicate/unknown devices, missing environment
  values, invalid PR declarations, and empty discovery fail explicitly before
  hardware use.
- [x] **TR-CONFIG-AC-03:** CLI PR numbers union with configured PR numbers, and
  unrelated validation methods remain visible as skips.

## Interfaces and compatibility

- [x] **TR-CONFIG-AC-04:** `--config`, `--device`, `--pattern`,
  `--validation-pr`, and verbosity retain documented semantics.
- [x] **TR-CONFIG-AC-05:** Resolved secrets are not written into `run.json` or
  the configuration model's public metadata.

## Quality attributes

- [x] **TR-CONFIG-AC-06:** Invalid configuration returns a distinct CLI
  configuration failure rather than a false test result.

## Verification evidence

- `tests.unit.test_config` — parsing, environment, duplicate, orchestration
  metadata, and CLI validation coverage; reconciled 2026-08-10.
- `tests.unit.test_validation_tests` — selected and skipped validation methods;
  reconciled 2026-08-10.
- Full unit suite and package build — required after documentation adoption.

## Acceptance rule

Changes are acceptable only when examples, CLI behavior, error semantics,
selection tests, and this spec remain synchronized and no resolved secret is
serialized.
