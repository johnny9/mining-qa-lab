# Lab orchestrator deployment contract

## Contents

- [Standard layout](#standard-layout)
- [Read-only inspection](#read-only-inspection)
- [Initial installation](#initial-installation)
- [Prepare an update](#prepare-an-update)
- [Idle cutover](#idle-cutover)
- [Verification](#verification)
- [Rollback](#rollback)
- [Unit changes](#unit-changes)
- [Failure diagnosis](#failure-diagnosis)
- [Safety and reporting](#safety-and-reporting)

## Standard layout

Prefer this portable user-service layout unless observed deployment constraints
require different absolute paths:

```text
$HOME/.local/src/mining-qa-lab/                 source checkout
$HOME/.local/opt/mining-qa-lab/releases/SHA/   immutable code + service venv
$HOME/.local/opt/mining-qa-lab/current          link to active release
$HOME/.config/mining-qa-lab/orchestrator.yaml   private configuration
$HOME/.config/mining-qa-lab/orchestrator.env    optional mode-0600 secrets
$HOME/.local/state/mining-qa-lab/            SQLite, token, jobs, pins
$HOME/.local/state/mining-qa-testcode/                runner artifacts
$HOME/.local/lib/mining-qa-testcode/                  managed worker source + venv
```

The service venv is inside one release. The worker venv is outside releases and
is managed by the orchestrator's `testcode` policy. Never point both at one venv.
Each release also contains a non-secret provenance record with the approved
credential-free repository identifier, full commit SHA, and Git tree SHA.

## Read-only inspection

Resolve the actual unit rather than assuming its name or path:

```bash
systemctl --user show miner-orchestrator.service \
  --property=LoadState,ActiveState,SubState,FragmentPath,ExecStart,WorkingDirectory
systemctl --user status miner-orchestrator.service --no-pager
journalctl --user-unit miner-orchestrator.service --lines=100 --no-pager
```

Run the bundled bounded inspector, adding candidate validation paths when known:

```bash
python3 skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py \
  --unit miner-orchestrator.service \
  --health-url http://127.0.0.1:8765/api/v1/health

python3 skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py \
  --unit miner-orchestrator.service \
  --health-url http://127.0.0.1:8765/api/v1/health \
  --orchestrator "$HOME/.local/opt/mining-qa-lab/current/.venv/bin/miner-orchestrator" \
  --config "$HOME/.config/mining-qa-lab/orchestrator.yaml"
```

Health `status: ok` proves only that the API answered with its current config
revision and queue counts. Inspect recent background-loop errors separately.

## Initial installation

Do not execute these mutations unless initial deployment is requested.

1. Create the source, release, config, state, artifact, and worker directories
   with user ownership. Make config and secret files private, and create every
   configured writable directory before enabling the service.
2. Clone the approved repository into the source checkout. Resolve one full
   commit SHA and review its relationship to the requested ref.
3. Prepare that exact release using the procedure below.
4. Create private YAML outside the release and validate it with the candidate.
5. Copy the bundled unit to
   `$HOME/.config/systemd/user/miner-orchestrator.service`, review every writable
   path, run `systemd-analyze verify`, and call `systemctl --user daemon-reload`.
6. Atomically create `current`, then enable/start only when requested.
7. Verify unit, API, revision, journal, and state ownership. Enabling user linger
   is a separate host-policy change and requires explicit authority.

Never commit the resulting YAML, environment file, token, device coordinates,
unit overrides, or local wrapper.

## Prepare an update

Preparation must not change the live `current` link or running process.

1. Inspect `git status`, origin URL, current branch, remote default, current
   release target, and available space.
2. Fetch the approved source. Record the full target SHA; never deploy an
   unrecorded moving branch name.
3. Create `releases/<full-sha>` without overwriting an existing directory.
   Export only tracked source for that SHA, record the credential-free source,
   commit, and tree, then create its `.venv`.
4. Install the `mining-qa-lab` project into that release venv.
5. Run full unit tests, spec integrity, skill validation, package build, and
   whitespace checks from the exact candidate source as repository policy requires.
6. Validate the live private YAML using the candidate's `miner-orchestrator`.
7. Review database changes for backward compatibility and require an explicit
   backup/forward/restore plan for any migration a code-link rollback cannot undo.
8. Do not mark the release ready if any required check or config validation fails.

Example command shape; resolve variables to inspected explicit paths before use:

```bash
git -C "$HOME/.local/src/mining-qa-lab" archive TARGET_FULL_SHA | \
  tar -x -C "$HOME/.local/opt/mining-qa-lab/releases/TARGET_FULL_SHA"
python3 -m venv \
  "$HOME/.local/opt/mining-qa-lab/releases/TARGET_FULL_SHA/.venv"
"$HOME/.local/opt/mining-qa-lab/releases/TARGET_FULL_SHA/.venv/bin/python" \
  -m pip install --no-input --editable \
  "$HOME/.local/opt/mining-qa-lab/releases/TARGET_FULL_SHA"
```

`TARGET_FULL_SHA` is explanatory text, not a command to paste unchanged.

## Idle cutover

Immediately before service mutation:

1. Query `/api/v1/health` and require `running_assignments` to be zero.
2. If work is running, do not cancel, kill, or stop merely to proceed. Wait only
   within an agreed bounded window; otherwise report the candidate as prepared
   but activation deferred.
3. Record `readlink -f <deploy-root>/current` as the rollback target.
4. Stop with `systemctl --user stop miner-orchestrator.service` and allow
   graceful completion. If a forced stop becomes necessary, report hardware
   state as uncertain and require physical inspection before retry.
5. Verify inactive. Create a new symlink name beside `current`, then atomically
   rename it over `current` on the same filesystem.
6. Start the service. Reload the systemd manager first only if the unit changed.

Queued assignments are durable and may resume after restart. Running assignments
are the safety gate because they may own hardware and cleanup state. The health
check is not a drain lock: a claim can race the interval before stop. Keep that
interval as short as possible and report this limitation until drain support exists.

## Verification

Collect and keep separate:

- exact active release target, SHA, and matching non-secret provenance record;
- `systemctl --user is-active` and `show` state;
- bounded recent journal with no repeated exceptions or secret values;
- `/api/v1/health` status, config revision, and queue counts;
- candidate config digest versus the live health revision;
- SQLite/state/config paths still outside the release;
- managed worker checkout/venv still distinct from the service release/venv.

Do not call this a hardware validation. Run HIL only under a separate explicit
request, then verify device cleanup independently.

## Rollback

Restoring the recorded previous code link is the declared failure response of
an authorized update. A standalone rollback, database restore, or config
rollback is a separate operation and requires its own authority.

1. Preserve failed-candidate logs and exact SHA.
2. Stop the service gracefully and verify inactive.
3. Atomically point `current` back to the recorded previous release.
4. Start and repeat all service/API/config/log verification.
5. Keep the failed candidate for diagnosis. Do not delete application state.

If the candidate performed an incompatible database migration, stop. A code
symlink rollback is insufficient; use the migration's reviewed restore plan.

## Unit changes

Start from `assets/miner-orchestrator.service`. Review:

- `ExecStartPre`, `ExecStart`, and `WorkingDirectory` use `current`;
- environment/config/state paths are private and outside releases;
- the optional environment file stays read-only inside the service sandbox;
- every `ReadWritePaths` entry is required by config, artifacts, or worker install;
- `PrivateDevices` is absent because local workers may need USB;
- network access remains available for GitHub, QA Status, SSH workers, and pools;
- graceful shutdown has no short timeout that would kill cleanup;
- bind/auth/firewall exposure matches the operator API spec.

Run `systemd-analyze verify` on the candidate unit. A syntax check does not
prove user-manager policy, path existence, permissions, device access, or live behavior.

## Failure diagnosis

Use bounded evidence:

```bash
systemctl --user status miner-orchestrator.service --no-pager
journalctl --user-unit miner-orchestrator.service --lines=200 --no-pager
```

Common distinctions:

- `ExecStartPre` failure means candidate config or executable validation failed.
- `203/EXEC` means an executable/path/permission problem, not app health.
- `status=2` from `miner-orchestrator` is a config or startup contract failure.
- `Read-only file system` or `Permission denied` may mean a missing unit write path.
- API health failure with an active unit can mean bind, startup, or network policy.
- API `ok` with repeated journal exceptions is degraded background operation.
- Startup recovery marking a run error is expected fail-closed evidence after interruption.

## Safety and reporting

- Never print environment/token files or serialize resolved secrets.
- Never edit SQLite/WAL by hand while or after service ownership without a
  separate recovery plan.
- Never use lease release or service restart as proof of physical cleanup.
- Report exact commands/checks, source and deployed SHAs, observed idle state,
  unit/API/log results, config revision, rollback target, and all unverified classes.
