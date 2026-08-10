---
name: setup-lab-orchestrator-service
description: Set up the mining-qa-lab orchestrator as a local systemd user service using an exact-SHA release, private configuration, separate durable state and worker environments, validation, and post-start checks. Use for a first local deployment or for preparing a host that does not yet run miner-orchestrator. Do not use for updating an existing deployment or running hardware gates.
---

# Set Up the Lab Orchestrator Service

Install one exact release without mixing code, private configuration, durable
state, or the separately managed test runner.

## Establish scope

1. Read repository `AGENTS.md`, all files under
   `specs/lab-orchestrator/service-deployment/`, and
   `skills/manage-lab-orchestrator-deployment/references/deployment-contract.md`.
2. Treat setup, enabling, starting, linger, firewall, USB permission, and
   private-config changes as separate mutations. Perform only those explicitly
   requested. Otherwise inspect and produce a host-specific setup plan.
3. Confirm this is an initial install. If a unit, `current` link, release tree,
   config, or state already exists, stop and route the work through
   `$update-lab-orchestrator-deployment` or
   `$manage-lab-orchestrator-deployment`; never overwrite it.

## Resolve the deployment

1. Inspect the approved credential-free repository URL, exact target commit,
   Python version, systemd user manager, available space, and required local or
   SSH worker access.
2. Resolve explicit absolute paths for source, releases, `current`, private
   YAML/env, SQLite state, artifacts, and worker checkout/venv. Keep the service
   venv inside its release and the worker venv outside every release.
3. Inventory every path the unit must write from the validated YAML. Do not
   infer firewall, linger, group, udev, or operating-system changes.

## Prepare before activation

1. Create private directories with restrictive ownership and modes.
2. Export the exact tracked commit into a new `releases/<full-sha>` directory;
   never deploy a moving branch or dirty checkout. Record repository, full
   commit SHA, and Git tree SHA in `RELEASE_PROVENANCE`.
3. Create the release venv, install the project, and run the repository-required
   unit, spec, skill, package, and whitespace checks from that exact source.
4. Initialize private YAML outside the release. Replace every placeholder,
   keep secrets in named environment variables, and validate with the candidate
   executable. Do not print the YAML or environment file if it contains private
   lab coordinates or secret references.
5. Adapt the canonical unit at
   `skills/manage-lab-orchestrator-deployment/assets/miner-orchestrator.service`
   only to the resolved paths. Preserve graceful stop, filesystem restrictions,
   network access, and required USB access. Run `systemd-analyze verify`.

## Activate and verify

1. Atomically create the initial `current` link only after all preparation passes.
2. Reload the user manager and enable/start the unit only when authorized.
3. Use the bounded inspector at
   `skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py`.
   Verify the selected SHA/provenance, systemd active state, API health and
   matching config revision, bounded recent journal, external state paths, and
   distinct service/worker venvs.
4. Do not call API health a hardware, repository-polling, pool, or publication
   validation. Run preflight or HIL only under a separate request.

## Report

Name the exact SHA/tree and paths, checks actually run, unit/API/log/config
results, permissions or host-policy work left to the operator, and every
mutation not performed. Never claim a live install when only preparation or
source validation occurred.
