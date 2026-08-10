# ESP-Miner device adapters — intent

## Problem

Bonanza 1002/BZM and Gamma 602/BM1370 share AxeOS interfaces but have different
identity, firmware, and telemetry details. The runner needs common behavior
without pretending those hardware differences do not exist.

## Why it matters

One well-tested common adapter reduces duplicated write and cleanup logic while
model subclasses prevent a run from silently targeting the wrong board.

## Stakeholders

- **Bonanza/Gamma test operator** — expects correct identity and artifact rules.
- **Generic test author** — consumes common capabilities and normalized state.
- **Firmware developer** — gets comparable evidence across supported boards.

## Desired outcome

Both supported boards identify exactly, expose only configured capabilities,
normalize portable state, and share verified AxeOS pool, restart, telemetry,
log, and firmware behavior.

## Primary flow

1. The common adapter initializes configured AxeOS/serial/WebSocket interfaces.
2. A model subclass validates `boardVersion` and `ASICModel`.
3. Generic lifecycle and tests operate through common pool, state, telemetry,
   firmware, and cleanup methods.

## Alternate and failure flows

- A mismatched model fails during `start()` before mutation.
- Optional WebSocket falls back to REST; a required stream failing to start is
  an error.
- New and legacy pool schemas restore through equivalent contracts.

## Non-goals

- Supporting arbitrary ESP-Miner boards without an explicit identity profile.
- Representing Gamma as having separate bridge firmware.
- Exposing Bonanza-only health fields as required generic fields.
