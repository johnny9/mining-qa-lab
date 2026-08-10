# mining-qa-lab

`mining-qa-lab` is the private-side lab orchestrator for the Mining QA project.
It turns approved repository changes and operator requests into durable hardware
test gates. It keeps the lab inventory, assigns exclusive devices, optionally
installs firmware, starts the external test runner, and publishes one aggregate
gate result.

The hardware test suite is not bundled with this service. It lives in
[`mining-qa-testcode`](https://github.com/johnny9/mining-qa-testcode). When
`testcode.enabled` is true, the orchestrator resolves the configured branch,
pins one exact commit for each gate and host, installs that checkout into a
separate worker virtual environment, and runs its `miner-test` command. The two
repositories communicate through the versioned
[orchestration contract](contracts/orchestration-v1.md).

[`mining-qa-status`](https://github.com/johnny9/mining-qa-status) is the external
collector and presentation service. Testcode publishes detailed child results;
the lab orchestrator publishes only parent gate state and child-result links.

## What the service does

- validates revisioned YAML configuration for repositories, gates, hosts,
  devices, setups, test modules, and trust policy;
- ingests GitHub or Mining QA Status events, schedules, exact-SHA approvals, and
  manual requests without scheduling old work on first observation;
- plans setup/module assignments idempotently and supersedes stale queued pull
  request work without interrupting active device cleanup;
- persists runs, assignments, leases, and recovery state in SQLite WAL;
- resolves exact successful firmware artifacts and can perform board-checked
  ESP-Miner OTA when explicitly configured;
- resolves and installs an exact `mining-qa-testcode` revision before an
  assignment, without changing the orchestrator service environment;
- executes workers locally or over SSH with agent forwarding disabled and an
  allowlisted environment;
- provides a bounded REST API, local operator UI, health endpoint, worker logs,
  and result-pointer records;
- publishes aggregate gate results and immutable links to detailed child
  results.

## Install for development

Python 3.11 or newer is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
miner-orchestrator init-config orchestrator.local.yaml
```

The generated YAML is an example. Keep the real file untracked because it
contains private lab coordinates. Replace every placeholder and use absolute
paths for service state and managed worker checkouts.

Validate it before starting anything:

```bash
miner-orchestrator --config orchestrator.local.yaml validate
```

Validation prints the configuration SHA-256 digest. It does not contact
hardware.

## Run

Start the API, UI, repository watchers, planner, and assignment queue:

```bash
miner-orchestrator --config orchestrator.local.yaml serve
```

Poll and plan once without starting the long-running service:

```bash
miner-orchestrator --config orchestrator.local.yaml poll-once
```

Queue a manual gate for one exact source commit:

```bash
miner-orchestrator --config orchestrator.local.yaml \
  run firmware-smoke FULL_40_CHARACTER_COMMIT_SHA --branch main --wait
```

The `--wait` form executes assignments until that run finishes. A manual run
can touch hardware, install testcode, or deploy firmware according to the YAML;
use it only for an authorized target.

## How testcode installation works

The relevant YAML shape is:

```yaml
testcode:
  enabled: true
  repository: johnny9/mining-qa-testcode
  ref: main
  install_timeout: 300

lab:
  hosts:
    controller:
      transport: local
      testcode:
        checkout: /var/lib/mining-qa-testcode/source
        venv: /var/lib/mining-qa-testcode/runner-venv
        python: python3
```

For the first assignment on a gate/host, the service resolves `ref` to a full
commit SHA, prepares the checkout and separate virtual environment, and records
the pin under the service state directory. Later assignments in the same gate
reuse that SHA even if `main` moves. The runner independently checks its
repository and SHA before constructing hardware objects. Installation failure
stops the assignment before firmware deployment or testing.

The service virtual environment and the worker virtual environment must never
be the same directory.

## API and state

The default local endpoint is `http://127.0.0.1:8765`. The service exposes its
exact OpenAPI document at `/openapi.json`; the feature specs define endpoint
ownership, authorization, state transitions, and failure behavior.

Bearer authentication is the default. A generated token is stored under the
configured state directory. Authentication can be disabled only with an
explicit allowed-network policy. Never put resolved secrets in YAML.

Durable data belongs under `controller.state_dir`:

```text
orchestrator.sqlite3              runs, assignments, events, leases, cursors
jobs/GATE/ASSIGNMENT/worker.log   bounded private worker output
jobs/GATE/ASSIGNMENT/result-pointer.json
testcode/GATE/HOST.json           exact testcode pin
api-token                         local bearer token when enabled
```

## Deploy as a service

For human-readable systemd setup, updates, idle cutover, verification, and
rollback, read [Deploying the lab orchestrator](docs/ORCHESTRATOR_DEPLOYMENT.md).
The example user unit is at
[miner-orchestrator.service](skills/manage-lab-orchestrator-deployment/assets/miner-orchestrator.service).

Agents should use the repository-owned deployment skill:

```bash
./scripts/validate-codex-skills
./scripts/manage-codex-skills status manage-lab-orchestrator-deployment
./scripts/manage-codex-skills install manage-lab-orchestrator-deployment
```

Installation creates a link back to this repository and refuses to replace an
existing skill. A skill provides procedure, not permission to restart a
service, change private configuration, deploy firmware, or run hardware tests.

## Specifications and agent guidance

- [AGENTS.md](AGENTS.md) defines repository working and safety rules.
- [specs/OVERVIEW.md](specs/OVERVIEW.md) explains the boundary between the lab,
  testcode, and status services.
- [specs/INDEX.md](specs/INDEX.md) lists every lab and project-tooling feature.
- [specs/STORY-MAP.md](specs/STORY-MAP.md) navigates features by operator
  outcome.
- [specs/README.md](specs/README.md) explains how specifications are structured.

## Development verification

These tests do not contact real hardware:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v
./scripts/validate-codex-skills
python3 -m build --no-isolation
git diff --check
```

Hardware validation, live service changes, firmware deployment, and external
publication are separate operations and must be explicitly authorized and
reported separately.
