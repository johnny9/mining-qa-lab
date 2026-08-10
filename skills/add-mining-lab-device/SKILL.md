---
name: add-mining-lab-device
description: Walk through adding a mining device to a mining-qa-lab private configuration, including host placement, stable identity, API and USB coordinates, setup role mapping, runner profile compatibility, validation, and read-only preflight. Use when onboarding, replacing, or modeling a physical device or setup in the lab inventory. Do not run gates, flash firmware, or expose private coordinates unless separately authorized.
---

# Add a Mining Lab Device

Build a validated inventory entry from observed hardware facts, then prove only
the read-only checks that were actually performed.

## Establish the boundary

1. Read repository `AGENTS.md`, all files under
   `specs/lab-orchestrator/configuration-and-control-plane/` and
   `specs/lab-orchestrator/lab-inventory-and-preflight/`, plus
   `src/mining_qa_lab/orchestrator.example.yaml` and the active config schema in
   `src/mining_qa_lab/config.py`.
2. Locate the private active YAML without printing it. Read-only discovery and
   candidate validation do not authorize changing live config, probing a host,
   opening USB, flashing firmware, or running a gate.
3. Decide whether the request adds one device to an existing setup, creates a
   new setup, replaces coordinates behind a stable logical ID, or also needs a
   new host. Preserve unrelated entries.

## Collect observed facts

1. Choose stable lowercase IDs for the host, device, and setup. Keep human
   labels separate from private addresses and serial paths.
2. Record device `name`, testcode-compatible `type`, owning `host`, `enabled`
   state, available API/WebSocket addresses, persistent `/dev/serial/by-id`
   path and USB identity when applicable, expected board identity, and useful
   non-secret tags.
3. For a new host, choose `local` or `ssh`, explicit worker checkout/venv paths,
   Python command, work paths, and bounded parallelism. Never reuse the service
   release venv for testcode or enable SSH agent forwarding.
4. Define a setup on one host with stable device roles, a runner profile that
   exists in the pinned `mining-qa-testcode` source, and an explicit platform
   key when the derived type set is not the intended public identity. If
   `runner_devices` is needed, map it to the names expected by that profile.

## Validate a candidate first

1. Copy the current private YAML to a mode-restricted temporary candidate or
   use a revision-checked control-plane draft. Never edit the tracked example
   into a live inventory.
2. Add the smallest host/device/setup changes. Use environment or file
   references for secrets; never add plaintext secret-like fields.
3. Run the deployed or candidate `miner-orchestrator --config <candidate>
   validate`. Resolve every host, device, setup, module-interface, and gate
   cross-reference error before offering activation.
4. Review existing gates: add the setup only where that device is intentionally
   qualified and where every selected test module supports its type/interfaces.
   Treat gate expansion as a separate policy decision, not an onboarding default.

## Activate and preflight

1. If live mutation is explicitly authorized, prefer the authenticated UI or
   revision-checked resource API so validation, `If-Match`, backup, and atomic
   replacement remain enforced. For an offline file workflow, preserve a
   restorable backup and replace atomically.
2. Confirm the service reports the new configuration revision.
3. If read-only live probing is authorized, discover USB on the owning host,
   probe the device, and run setup preflight through the operator UI/API.
   Compare observed identity with the declaration. Do not reboot, flash, mine,
   claim a lease, or run testcode as part of preflight.
4. Call the device configured but not operational until current API/USB/setup
   preflight succeeds. Preflight still does not prove mining health or runner
   capability.

## Report

Name the logical IDs, host/setup roles, candidate and active config revisions,
validation/preflight results, gates deliberately changed or left unchanged,
private values omitted from the report, and any unverified physical behavior.
