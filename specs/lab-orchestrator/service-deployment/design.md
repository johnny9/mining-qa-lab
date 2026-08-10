# Service deployment — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Human runbook | Explain initial deployment, update, rollback, and diagnosis | `docs/ORCHESTRATOR_DEPLOYMENT.md` |
| Deployment skill | Guide agents through evidence-backed, authorized operations | `skills/manage-lab-orchestrator-deployment/SKILL.md` |
| Inspector | Read systemd, config validation, and API health without mutation | `skills/manage-lab-orchestrator-deployment/scripts/inspect_deployment.py` |
| Unit example | Define the portable systemd user-service baseline | `skills/manage-lab-orchestrator-deployment/assets/miner-orchestrator.service` |
| Orchestrator | Validate config, serve API, recover state, and run work | `src/miner_testcode/orchestrator/cli.py`, `src/miner_testcode/orchestrator/web.py` |

## Interfaces and contracts

### CLI

- Service validation uses `<release>/.venv/bin/miner-orchestrator --config
  <config> validate`; serving uses the same executable/config with `serve`.
- Operators use `systemctl --user` for daemon reload, enable, start, stop,
  restart, and status, and `journalctl --user-unit` for bounded logs.
- The bundled inspector is read-only and reports service, config, health, and
  whether observed running-assignment state permits a planned restart.

### Configuration

- The private orchestrator YAML lives outside release directories and retains
  its schema/version contract. Absolute state, runner profile, worker checkout,
  worker venv, and artifact paths must match unit sandbox write allowances.
- The example layout uses user-owned XDG-style config, state, library, and
  application directories; operators may choose other absolute paths by
  updating the unit and documentation together.

### Environment

- Secrets use a mode-0600 environment file or the orchestrator's existing
  generated token file. The environment file is optional and never committed.
- The service venv belongs to one immutable release. Managed worker testcode
  uses the distinct per-host checkout/venv configured under `testcode`.

### Python API

- None. Deployment consumes supported CLI and HTTP contracts and does not add
  an in-process extension API.

### HTTP or external protocols

- `GET /api/v1/health` supplies bounded API status, config revision, and queued/
  running assignment counts. A planned stop requires an observed running count
  of zero immediately before cutover.
- Git resolves the selected deployment revision. Network/package access may be
  required while preparing a candidate, but cutover always names the exact SHA.

### Files, artifacts, payloads, and persistent state

- `<deploy-root>/releases/<full-sha>/` is immutable after validation, records
  credential-free repository/commit/tree provenance, and owns the release venv.
  `<deploy-root>/current` is an atomically replaced symlink.
- YAML, secret environment, SQLite/WAL, jobs, artifacts, managed worker source/
  venv, and the prior release remain outside or alongside—not inside—`current`.
- systemd journal output is operational evidence but may not contain tokens or
  private environment contents.

## Contract constraints

### Required invariants

- Every release and handoff record identifies a full source commit SHA.
- Candidate installation, unit/package checks, and config validation complete
  before service stop or `current` replacement.
- A planned update observes zero running assignments immediately before stop,
  minimizes the remaining check/stop race, and never represents that observation
  as an application drain lock.
- Shutdown remains graceful; forced termination never implies hardware cleanup.
- Symlink cutover is atomic and the previous release target is retained.
- Startup verification distinguishes unit state, API reachability, config
  revision, background-loop logs, and HIL rather than collapsing them into one claim.
- Configuration, secrets, durable state, and worker environments survive code
  release replacement without being copied into a release.

### Forbidden behavior

- Do not update code or dependencies in place under a running release.
- Do not stop/cancel active work merely to make an update proceed.
- Do not delete or rewrite SQLite/WAL, private YAML, token files, artifacts, or
  previous release during routine update.
- Do not use `git reset --hard`, a moving unrecorded ref, or automatic fallback
  that hides a failed candidate.
- Do not run HIL, firmware deployment, service mutation, or rollback without
  authorization appropriate to that action.

## Data and state

Deployment state is the exact candidate/current/previous SHA and filesystem
targets plus current systemd/API observations. Application truth remains in
the external orchestrator state directory and is not migrated by code cutover.

## Control and data flow

1. Inspect unit, paths, source/ref, current SHA, config digest, health, and logs.
2. Fetch/read the desired source and prepare an exact release without activation.
3. Run automated checks and validate the private config with the candidate CLI.
4. Recheck zero running assignments, stop gracefully, and switch `current`.
5. Start and verify unit/API/config/log signals; report exact deployed SHA.
6. On failure, stop, atomically restore the previous link, restart, and verify.

## Failure and recovery

- Dirty/ambiguous source, dependency failure, invalid config, or failed checks
  block activation and leave the current service unchanged.
- Active assignments block planned stop. Wait and recheck instead of cancelling.
- Failed activation retains logs and candidate, restores the previous link, and
  does not mutate application state.
- Forced or host interruption invokes normal fail-closed startup recovery and
  requires separate physical cleanup confirmation.

## Compatibility and migration

- Release directories permit side-by-side Python/dependency versions. Database
  schema changes require their own forward/rollback compatibility plan before
  activation; symlink rollback alone cannot reverse an incompatible migration.
- Unit/config path changes are reviewed as deployment-interface changes and
  rolled out before relying on new code assumptions.

## Resource and operational constraints

- Keep at least current and previous releases plus enough disk for candidate
  venv/package installation. Retention beyond that is an operator policy.
- Package/network, service stop, journal, and HTTP checks are bounded. A
  graceful shutdown may take as long as an already-running assignment cleanup.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Repository skills](../../project-tooling/repository-skills/SPEC.md) | Packages and installs the deployment workflow for agents. |
| [Operator API and UI](../operator-api-and-ui/SPEC.md) | Supplies CLI, API health, auth, and logs visible at deployment time. |
| [Configuration and control plane](../configuration-and-control-plane/SPEC.md) | Keeps validated private YAML outside releases. |
| [Persistence, leases, and recovery](../persistence-leases-and-recovery/SPEC.md) | Keeps durable state outside releases and defines interrupted-work recovery. |
| [Testcode bootstrap](../testcode-bootstrap/SPEC.md) | Owns the separate worker source/venv and never updates the service release. |

## Verification approach

Validate skill metadata/resources, installer conflict behavior, inspector
success/failure/size bounds, systemd unit syntax/security properties, all
documentation links, spec integrity, full unit tests, and package build. Keep
live install/update/rollback and HIL as separate explicitly authorized evidence.
