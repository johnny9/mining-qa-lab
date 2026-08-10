# Deploying the lab orchestrator

This guide explains how to run `miner-orchestrator` continuously with a systemd
user service, update it safely, and roll it back if a new version fails.

The important idea is simple: prepare new code beside the running version. Stop
the service only when no hardware test is running, switch one link, and start it
again. Keep configuration and state outside the code directory.

## What each directory does

```text
Git checkout -> release named by commit -> current link -> systemd service

Private YAML and secrets -------------------------------> service
SQLite, jobs, artifacts, and worker testcode -----------> service
```

- **Source checkout:** where you fetch and review repository changes.
- **Release:** one exact Git commit with its own Python virtual environment.
- **Current link:** points systemd at the selected release.
- **Configuration:** your private repositories, gates, devices, and paths.
- **State:** the SQLite database, jobs, testcode pins, API token, and artifacts.
- **Worker testcode:** the separate checkout and venv used to run `miner-test`.

Updating worker testcode does **not** update this service. The `testcode` section
of orchestrator YAML updates only the test runner used by assignments. Updating
the orchestrator itself requires the release change described here.

## Recommended paths

This example runs as your normal Linux user:

```text
~/.local/src/miner-testcode/                 source checkout
~/.local/opt/miner-testcode/releases/SHA/   releases
~/.local/opt/miner-testcode/current          active-release link
~/.config/miner-testcode/orchestrator.yaml   private configuration
~/.config/miner-testcode/orchestrator.env    optional private secrets
~/.local/state/miner-orchestrator/            database and orchestrator jobs
~/.local/state/miner-testcode/                test artifacts
~/.local/lib/miner-testcode/                  worker testcode checkout and venv
```

You can use other absolute paths. If you do, update the YAML and systemd unit
together. Do not copy private YAML, tokens, state, or artifacts into a release.

## Before installation

You need:

- Linux with systemd user services;
- Git and Python 3.11 or newer;
- Python's `venv` support and package-index access;
- permission to use any configured USB/serial devices;
- the exact repository revision you intend to deploy.

Do not put tokens in the repository or command line. If the service needs
environment tokens, create `~/.config/miner-testcode/orchestrator.env` with mode
0600 and put only named `KEY=value` entries there. Never print that file.

## Install the first release

The following is an example. Read each path before running it.

```bash
source_root="$HOME/.local/src/miner-testcode"
deploy_root="$HOME/.local/opt/miner-testcode"
config_root="$HOME/.config/miner-testcode"
state_root="$HOME/.local/state/miner-orchestrator"
artifact_root="$HOME/.local/state/miner-testcode"
worker_root="$HOME/.local/lib/miner-testcode"
approved_repository="https://github.com/johnny9/miner-testcode.git"

install -d -m 0700 \
  "$source_root" "$deploy_root/releases" "$config_root" "$state_root" \
  "$artifact_root" "$worker_root"
git clone "$approved_repository" "$source_root"
git -C "$source_root" status --short --branch
test "$(git -C "$source_root" remote get-url origin)" = "$approved_repository"
release_sha="$(git -C "$source_root" rev-parse --verify 'HEAD^{commit}')"
release_tree="$(git -C "$source_root" rev-parse --verify "$release_sha^{tree}")"
release="$deploy_root/releases/$release_sha"
test ! -e "$release" && test ! -L "$release"
install -d -m 0700 "$release"
git -C "$source_root" archive "$release_sha" | tar -x -C "$release"
{
  printf 'repository=%s\n' "$approved_repository"
  printf 'commit=%s\n' "$release_sha"
  printf 'tree=%s\n' "$release_tree"
} > "$release/RELEASE_PROVENANCE"
chmod 0444 "$release/RELEASE_PROVENANCE"
python3 -m venv "$release/.venv"
"$release/.venv/bin/python" -m pip install --no-input --editable "$release[orchestrator]"
```

Initialize and edit the private configuration:

```bash
"$release/.venv/bin/miner-orchestrator" init-config "$config_root/orchestrator.yaml"
chmod 0600 "$config_root/orchestrator.yaml"
"$release/.venv/bin/miner-orchestrator" \
  --config "$config_root/orchestrator.yaml" validate
```

The generated YAML is an example, not live lab configuration. Replace every
placeholder device, repository, profile, USB identity, and path. In particular,
use absolute state, artifact, worker checkout, and worker venv paths that agree
with the systemd unit's writable directories.

Run the repository checks before selecting the release:

```bash
cd "$release"
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
./scripts/validate-codex-skills
python3 -m build --no-isolation
git -C "$source_root" diff-tree --check --root -r "$release_sha"
```

Create the initial link only after checks and config validation pass:

```bash
ln -s "$release" "$deploy_root/current.next"
mv -T "$deploy_root/current.next" "$deploy_root/current"
```

Install the example user unit:

```bash
unit_source="$release/skills/manage-lab-orchestrator-deployment/assets/miner-orchestrator.service"
unit_target="$HOME/.config/systemd/user/miner-orchestrator.service"
install -D -m 0644 "$unit_source" "$unit_target"
systemd-analyze verify "$unit_target"
systemctl --user daemon-reload
systemctl --user enable --now miner-orchestrator.service
```

The unit deliberately does not use `PrivateDevices=true`; local workers may
need USB. It gives write access only to the example config, state, artifacts,
and worker directories. The optional environment file is made read-only again
inside the otherwise writable config directory. Add another writable path only
when your reviewed YAML requires it.

## Check the service

Use the read-only inspector:

```bash
python3 "$release/skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py" \
  --unit miner-orchestrator.service \
  --health-url http://127.0.0.1:8765/api/v1/health \
  --orchestrator "$deploy_root/current/.venv/bin/miner-orchestrator" \
  --config "$config_root/orchestrator.yaml"
```

Also inspect a small amount of recent log output:

```bash
systemctl --user status miner-orchestrator.service --no-pager
journalctl --user-unit miner-orchestrator.service --lines=100 --no-pager
```

Check five things separately:

1. systemd says the service is active;
2. `/api/v1/health` answers and reports the expected config revision;
3. recent logs do not show a repeating background error;
4. the selected `current` link names the expected full commit SHA;
5. `RELEASE_PROVENANCE` names the approved repository and expected commit/tree.

API health does not prove that hardware, repository polling, pools, or
publication are healthy. Those need their own checks.

## Update to new code

An update has two phases: prepare while the old service runs, then make a short
idle switch.

### 1. Prepare the candidate

```bash
git -C "$source_root" status --short --branch
test "$(git -C "$source_root" remote get-url origin)" = "$approved_repository"
git -C "$source_root" fetch --prune origin
target_sha="$(git -C "$source_root" rev-parse --verify 'origin/main^{commit}')"
target_tree="$(git -C "$source_root" rev-parse --verify "$target_sha^{tree}")"
candidate="$deploy_root/releases/$target_sha"
test ! -e "$candidate" && test ! -L "$candidate"
install -d -m 0700 "$candidate"
git -C "$source_root" archive "$target_sha" | tar -x -C "$candidate"
{
  printf 'repository=%s\n' "$approved_repository"
  printf 'commit=%s\n' "$target_sha"
  printf 'tree=%s\n' "$target_tree"
} > "$candidate/RELEASE_PROVENANCE"
chmod 0444 "$candidate/RELEASE_PROVENANCE"
python3 -m venv "$candidate/.venv"
"$candidate/.venv/bin/python" -m pip install --no-input --editable "$candidate[orchestrator]"
```

Run the candidate checks before stopping the current service:

```bash
current_sha="$(basename "$(readlink -f "$deploy_root/current")")"
git -C "$source_root" diff --check "$current_sha..$target_sha"
cd "$candidate"
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python \
  -m unittest discover -s tests/unit -v
./scripts/validate-codex-skills
python3 -m build --no-isolation
"$candidate/.venv/bin/miner-orchestrator" \
  --config "$config_root/orchestrator.yaml" validate
```

Record `current_sha` and `target_sha` in the update report. If a release
directory already exists, inspect and reuse it only if its exact contents and
checks are trusted; never overwrite it. Review any database-model or migration
change before cutover. A code-link rollback cannot undo an incompatible
database migration, so such a change needs a separate backup/restore plan.

### 2. Switch only when idle

Immediately before stopping, run the inspector with `--require-idle`. It must
report `running_assignments: 0` and `safe_to_restart: true`.

If a test is running, wait. Do not cancel it or kill the service just to finish
the update. Agree on a bounded wait; if it does not become idle, leave the
running service unchanged and report the candidate as prepared but deferred.

The health check is only an observation, not a drain lock. New work could be
claimed between the check and stop. Keep that interval as short as possible and
report this remaining race until the orchestrator gains a drain control.

```bash
previous="$(readlink -f "$deploy_root/current")"
systemctl --user stop miner-orchestrator.service
systemctl --user is-active miner-orchestrator.service
ln -s "$candidate" "$deploy_root/current.next"
mv -Tf "$deploy_root/current.next" "$deploy_root/current"
systemctl --user start miner-orchestrator.service
```

`is-active` should report `inactive` after the stop, so that particular command
normally returns a nonzero status. Verify the new service using the five checks
above. Keep `previous` and the old release.

If the unit file changed, review and install the new unit, run
`systemd-analyze verify`, and call `systemctl --user daemon-reload` before start.

## Roll back

An authorized update includes this fail-safe: if the new service does not start
or its health/config/log checks fail, restore the previous code release:

1. Save the failed candidate SHA and recent logs.
2. Stop the service and verify it is inactive.
3. Atomically point `current` back to the recorded `previous` directory.
4. Start the service and repeat all verification.

Do not delete the failed release, YAML, environment file, SQLite/WAL, jobs,
artifacts, API token, or worker testcode. They are evidence and recovery state.

A code rollback cannot undo an incompatible database migration. Database schema
changes need a reviewed backup and restore plan before deployment.

A standalone rollback, database restore, or config rollback is a separate
operation and needs its own explicit authorization.

## Common problems

- **`ExecStartPre` fails:** the executable or YAML did not validate.
- **`203/EXEC`:** systemd cannot execute the configured path.
- **Read-only filesystem:** add only the exact required path to
  `ReadWritePaths`, then verify the unit again.
- **Service active but health unavailable:** check bind address, port, network
  policy, and journal startup errors.
- **Health is okay but work is stuck:** health does not measure the background
  loop; inspect bounded journal and durable run/assignment state.
- **Service was killed during a test:** startup correctly marks interrupted work
  as error. Inspect the physical device and cleanup state before retrying.

## Install the agent skill

The repository includes the same safety workflow as an installable skill:

```bash
./scripts/validate-codex-skills
./scripts/manage-codex-skills status manage-lab-orchestrator-deployment
./scripts/manage-codex-skills install manage-lab-orchestrator-deployment
```

Installation creates a link under `${CODEX_HOME:-$HOME/.codex}/skills`. It never
replaces an existing file, directory, or different link. Because the link points
to this repository, reviewed skill updates become visible without copying files.
