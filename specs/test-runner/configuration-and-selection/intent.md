# Configuration and selection — intent

## Problem

Hardware tests need private device coordinates and environment-provided
credentials while remaining reproducible, selectable, and safe to publish.
Validation cases associated with a particular firmware PR must remain visible
without running against unrelated targets by default.

## Why it matters

Ambiguous selection can exercise the wrong device, publish misleading source
metadata, or run destructive validation unexpectedly. Persisting resolved
secrets would make local profiles and artifacts unsafe.

## Stakeholders

- **Test operator** — selects exact devices, test patterns, and opt-in cases.
- **Test author** — consumes typed runner/device/test settings.
- **Orchestrator assignment** — overrides pattern, device, and PR selection
  through the supported CLI.
- **Publisher** — receives stable public device labels rather than private
  configuration names.

## Desired outcome

One explicit TOML profile plus bounded CLI overrides resolves to an immutable
project configuration. Missing, duplicate, disabled, or invalid selection fails
before a device lifecycle begins.

## Primary flow

1. The runner loads and resolves the requested TOML file.
2. It validates runner, devices, interfaces, tests, publishers, and environment
   references, then applies CLI selection.
3. It discovers matching `MinerTestCase` methods for each enabled selected
   device and skips unselected PR validation cases explicitly.

## Alternate and failure flows

- A missing exact `${NAME}` variable, duplicate device, unknown device, invalid
  PR number, or empty discovery produces `ConfigError` and CLI exit status 2.
- A validation test not selected for any requested PR remains discovered and is
  reported as skipped.

## Non-goals

- Persisting resolved configuration or secrets.
- Inferring hardware selection from network discovery.
- Letting the orchestrator redefine runner profile semantics.
