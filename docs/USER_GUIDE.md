# Lab orchestrator user guide

This guide explains how a lab operator configures and uses
`mining-qa-lab`. It does not describe internal implementation rules. Those
belong in the [specifications](../specs/README.md).

## Before you start

You need:

- Python 3.11 or newer;
- a host that can reach the mining devices;
- local paths for service state and testcode work files;
- credentials supplied through environment variables;
- at least one configured project, gate, host, device, setup, and test module.

A manual gate may change device settings or install firmware. Confirm the
selected project, commit, device types, and firmware policy before you submit
it.

## Install the command

From the repository:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Create a starting configuration:

```bash
miner-orchestrator init-config orchestrator.local.yaml
```

The file is only an example. Replace every placeholder. Keep the real file
untracked because it contains private lab information. Use absolute paths for
service state, worker checkouts, and worker virtual environments.

Validate the file before starting the service:

```bash
miner-orchestrator --config orchestrator.local.yaml validate
```

Validation prints a SHA-256 digest for the configuration. It does not contact
hardware.

## Configure the test runner

The lab installs `mining-qa-testcode` into a worker environment. The worker
environment must be separate from the lab service environment.

A typical section looks like this:

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

For each gate and host, the lab resolves one exact testcode commit. Every
assignment in that gate uses the same commit. If installation or source
verification fails, the assignment stops before firmware deployment and
testing.

## Start the service

Run the API, web interface, project watchers, planner, and worker queue:

```bash
miner-orchestrator --config orchestrator.local.yaml serve
```

The default address is <http://127.0.0.1:8765>. The configured authentication
and network rules still apply.

To poll projects and create plans once, without keeping the service running:

```bash
miner-orchestrator --config orchestrator.local.yaml poll-once
```

## Run a gate in the web interface

Open <http://127.0.0.1:8765/trigger> and use **Run a gate locally**.

1. Select a project.
2. Select one of that project's gates.
3. Leave the source branch blank for the automatic `main` then `master`
   lookup, or select a configured branch.
4. Leave the commit blank for the latest commit on that branch, or enter an
   exact 40-character commit.
5. Select one or more device types offered by the gate.
6. Select **Queue local gate**.

The response shows the run ID, exact commit, selected branch, device types, and
initial status. The service saves the exact source revision before hardware
work begins.

### Run an untrusted pull request

The lower part of the same page lists open pull requests that are not covered
by the trusted-contributor policy.

Review the pull request and its exact head commit. Select the approval box only
when that exact revision is allowed to use lab hardware. The approval does not
apply to a later commit.

## Run a gate from the command line

Queue one configured gate for an exact source commit:

```bash
miner-orchestrator --config orchestrator.local.yaml \
  run firmware-smoke FULL_40_CHARACTER_COMMIT_SHA --branch main --wait
```

`--wait` lets the process execute assignments until the gate reaches a final
state. The configured gate may install testcode, deploy firmware, and change
device settings.

## View runs and artifacts

The home page lists recent gate runs. Select a run with archived files to open
the **Local artifact archive**.

The lab copies only files listed in testcode's artifact manifest. It checks the
size and SHA-256 digest of each file and keeps separate directories for retry
attempts. Text files can be viewed in the browser. Any archived file can be
downloaded.

By default, durable files live below the configured
`controller.state_dir`:

```text
orchestrator.sqlite3
jobs/GATE/ASSIGNMENT/worker.log
jobs/GATE/ASSIGNMENT/result-pointer.json
archive/GATE/ASSIGNMENT/attempt-N/
testcode/GATE/HOST.json
api-token
```

The archive contains private lab evidence. Monitor free disk space and define a
retention policy outside the service.

## Publication behavior

For a normal production setup, enable the `qa_status` integration.

- Testcode publishes the detailed child result and its selected private
  artifacts.
- The lab publishes the parent gate and links it to the child result.
- The lab also keeps its private local artifact copy.

The local copy never counts as successful remote publication. If required
publication is missing, the assignment is reported as an error.

## API access

The exact OpenAPI document is available at:

```text
http://127.0.0.1:8765/openapi.json
```

Bearer authentication is enabled by default. The generated token is stored
under `controller.state_dir`. Authentication may be disabled only when the
configuration also defines an allowed network policy.

Keep secrets in named environment variables. Do not put resolved passwords or
tokens in YAML.

## Common problems

### Configuration does not validate

Read the validation message, correct the named field, and run `validate`
again. Confirm that service and worker paths are absolute and that referenced
projects, gates, devices, setups, and modules exist.

### A device type is not available

The selected gate can show only device types provided by its configured setups
and accepted by its test modules. Check the gate target matrix and inventory.

### Testcode installation fails

Check the configured repository, ref, worker checkout, Python command, and
worker virtual environment. Do not point the worker virtual environment at the
lab service virtual environment.

### A run stopped after service restart

Interrupted work is not assumed safe. Inspect the run, worker log, device
state, and cleanup evidence before retrying or releasing hardware for another
run.

### Remote publication failed

Keep the local archive for diagnosis, but fix the publishing credentials or
service problem and rerun as appropriate. Do not treat the archive as a
published result.

For systemd installation, updates, logs, and rollback, use the
[deployment guide](ORCHESTRATOR_DEPLOYMENT.md).
