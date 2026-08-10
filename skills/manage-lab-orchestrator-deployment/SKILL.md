---
name: manage-lab-orchestrator-deployment
description: Inspect, install, update, restart, roll back, and troubleshoot the miner-testcode lab orchestrator deployment as a systemd user service. Use when working on a live or proposed miner-orchestrator service, its exact deployed revision, release/venv layout, private config and state boundaries, health checks, journal logs, safe idle cutover, or rollback. Do not use this skill to run hardware tests or deploy firmware unless the user separately requests those actions.
---

# Manage Lab Orchestrator Deployment

Manage the service from observed live state and preserve exact source, private
configuration, durable state, active cleanup, and rollback evidence.

## Establish the boundary

1. Read the repository `AGENTS.md` and
   `specs/lab-orchestrator/service-deployment/SPEC.md` with all companions.
2. Treat an explicit install, update, restart, or rollback request as authority
   only for that named deployment action. Otherwise perform read-only inspection.
3. Never infer authority to cancel work, edit private config, run HIL, deploy
   firmware, delete state/releases, change firewall/linger, or publish changes.
4. Do not assume the example unit is live. Resolve the actual unit fragment,
   executable, config, state directory, checkout/release, and current SHA.
5. Keep the service release/venv separate from the managed worker testcode
   checkout/venv configured under `testcode`.

## Route the task

- For status or diagnosis, run `scripts/inspect_deployment.py`, inspect the
  actual unit, and read a bounded recent journal. Do not mutate the service.
- For initial setup, update, restart, rollback, or unit changes, read
  [references/deployment-contract.md](references/deployment-contract.md)
  completely before acting.
- Use [assets/miner-orchestrator.service](assets/miner-orchestrator.service) as
  a portable baseline. Adapt only paths the observed config actually needs.
- Point humans to `docs/ORCHESTRATOR_DEPLOYMENT.md` in the repository; keep the
  skill focused on agent procedure.

## Execute a managed change

1. Record the live unit/path/config/state/current-release facts and the exact
   requested target SHA. Report conflicts before mutation.
2. Confirm source cleanliness, remote/ref identity, disk space, required Python,
   and rollback target. Fetching and candidate preparation must not alter live state.
3. Prepare a new exact-SHA release, provenance record, and service venv beside
   `current`. Run the repository-required unit, package, spec, skill, config,
   and migration-compatibility checks there.
4. Query health immediately before cutover. If any assignment is running, do
   not cancel or stop it. Wait only within an agreed bounded window; otherwise
   report the checked candidate as prepared but deferred. Zero running work is
   an observation, not a drain lock, so minimize the interval before stop and
   report that residual race until the application has a drain mechanism.
5. Record the previous symlink target, stop gracefully, verify stopped, replace
   `current` atomically, then start the service.
6. Verify the exact selected SHA, systemd active state, API health/config
   revision, and bounded journal. Keep these evidence classes distinct.
7. An authorized update includes restoring the previous code link when its
   candidate fails activation. Preserve diagnostics, stop, restore atomically,
   restart, and verify. Standalone rollback or database restore requires its
   own authority; routine code rollback never edits SQLite or private config.

## Report precisely

Name the previous and target SHAs and provenance, unit/config/state/release
paths, checks actually run, service/API/log results, whether assignments were
observed idle, and any rollback. State explicitly when live update, restart,
rollback, service security audit, or HIL was not performed.
