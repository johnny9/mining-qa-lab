---
name: create-mining-qa-gate
description: Define and validate a new mining-qa-lab gate from existing repositories, test modules, setups, triggers, change filters, result policy, timeouts, and optional verified firmware deployment. Use when adding or revising a gate policy or previewing its setup-by-module matrix. Do not create new hardware tests, run the gate, deploy firmware, or publish results unless separately requested.
---

# Create a Mining QA Gate

Express an operator-approved policy as a deterministic validated assignment
matrix without accidentally scheduling or executing hardware work.

## Establish the boundary

1. Read repository `AGENTS.md`, all files under
   `specs/lab-orchestrator/configuration-and-control-plane/` and
   `specs/lab-orchestrator/gate-planning-and-supersession/`, plus the active
   schema in `src/mining_qa_lab/config.py`.
2. Inspect existing repositories, modules, setups, artifacts, and nearby gates
   in the private config without exposing coordinates or secrets.
3. Separate policy creation from test implementation. A missing test module or
   device adapter belongs in `mining-qa-testcode`; do not invent its pattern,
   profile, capabilities, or lifecycle here.

## Design the gate

1. Choose a stable lowercase gate ID, clear name/description, and one configured
   repository.
2. Select only existing test modules and setups. For every setup-by-module pair,
   confirm device-type compatibility, required API/WebSocket/serial interfaces,
   runner profile availability, host placement, and expected platform key.
3. Set push, pull-request, and schedule triggers deliberately. Use unique
   schedule IDs and reviewed five-field cron expressions. Apply include/exclude
   path filters narrowly enough to avoid irrelevant hardware work.
4. Choose `required: all` unless the gate's contract genuinely succeeds when
   only one assignment passes. Set a bounded gate timeout consistent with the
   slowest matrix path.
5. Add `deployment` only when pre-test OTA is intended. Reference an artifact
   owned by the selected repository, list roles present in every target setup,
   require API and expected board identity, and keep a bounded reboot timeout.
   Gate configuration never authorizes a firmware upload.

## Validate before activation

1. Work on a mode-restricted candidate copy or a revision-checked control-plane
   draft. Preserve all unrelated config content.
2. Run `miner-orchestrator --config <candidate> validate` and resolve every
   reference, compatibility, interface, role, and policy error.
3. Derive and review the exact deterministic matrix: one assignment for every
   selected setup-by-module pair. Check matrix size, device contention,
   `max_parallel`, timeout budget, trigger breadth, and whether a firmware
   deployment would occur before each applicable assignment.
4. If live config mutation is explicitly authorized, use the authenticated UI
   or revision-checked resource API with the current ETag so the service
   validates, backs up, and atomically replaces YAML. Confirm the new revision,
   then call `/api/v1/gates/<gate-id>/validate` or use **Preview matrix**.

## Keep execution separate

Do not run the gate as a creation test. A manual run may acquire devices,
install testcode, flash firmware, alter miner configuration, publish child and
parent results, and consume pool credentials. It requires a separate request
that names or safely resolves the target repository revision.

## Report

Report the gate ID, repository, triggers and filters, required policy, timeout,
modules, setups, exact matrix, optional deployment behavior, candidate/active
config revision, checks performed, and whether live mutation or execution was
not performed.
