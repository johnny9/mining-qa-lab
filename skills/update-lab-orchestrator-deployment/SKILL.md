---
name: update-lab-orchestrator-deployment
description: Update an existing mining-qa-lab systemd user-service deployment to one exact reviewed commit using side-by-side release preparation, candidate validation, observed-idle cutover, verification, and automatic code-link rollback on activation failure. Use when deploying new orchestrator code or unit changes. Do not use for first installation, worker testcode updates, config-only edits, firmware deployment, or HIL.
---

# Update the Lab Orchestrator Deployment

Prepare new code beside the running release and keep the prior code link ready
until activation is proven.

## Establish authority and live facts

1. Read repository `AGENTS.md`, all files under
   `specs/lab-orchestrator/service-deployment/`, and
   `skills/manage-lab-orchestrator-deployment/references/deployment-contract.md`.
2. Treat an explicit update request as authority to prepare and activate only
   the named service code target, including restoring the prior code link if
   activation fails. Do not infer authority to edit private YAML, cancel work,
   restore a database, change host policy, update testcode, deploy firmware,
   run HIL, delete releases, or publish source changes.
3. Use `skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py`
   to resolve the actual unit, executable, source, releases, `current` target,
   config, state, worker environment, health endpoint, and active SHA. Do not
   assume the example layout is live.

## Prepare without changing live state

1. Confirm source cleanliness, credential-free origin identity, target ref and
   exact full SHA/tree, ancestry as relevant, disk space, Python, and retained
   rollback release. Fetching is preparation, not activation.
2. Export the exact target into a new immutable release and record repository,
   commit, and tree provenance. Never overwrite or silently trust an existing
   release directory.
3. Create its service venv and run the repository-required full unit, spec,
   skill, package, and whitespace checks. Validate the live private YAML using
   the candidate executable without printing private content.
4. Review database/schema compatibility. If rollback would require a database
   restore or forward migration, stop and obtain an explicit reviewed plan and
   authority before cutover.
5. If the unit changed, review every path/security difference and run
   `systemd-analyze verify`; do not install or reload it until cutover is authorized.

## Activate only when observed idle

1. Immediately before stopping, run the inspector with `--require-idle`. Require
   an active healthy service and `running_assignments: 0`.
2. If work is active, do not cancel or kill it. Wait only within an agreed
   bounded window; otherwise leave the live service unchanged and report the
   candidate as prepared but activation deferred.
3. Record the previous resolved link, stop gracefully, verify inactive,
   atomically replace `current`, install/reload a reviewed changed unit if
   applicable, and start. Minimize and report the race between the idle
   observation and stop because the current health API is not a drain lock.

## Verify or restore

1. Verify exact selected SHA and provenance, systemd active state, API health
   and matching config revision, bounded recent journal, unchanged external
   state/config paths, and distinct service/worker venvs.
2. If activation fails, preserve diagnostics, stop, atomically restore the
   recorded previous code link, restart, and repeat verification. Do not edit
   SQLite or private config as part of routine code rollback.
3. Do not claim hardware, polling, pool, cleanup, or publication health from a
   successful service check.

## Report

Name previous and target SHA/tree/provenance, resolved paths, candidate checks,
observed idle counts, unit/API/log/config results, the drain race, unit changes,
rollback action, and every class not tested. Distinguish prepared, deferred,
activated, verified, and restored states precisely.
