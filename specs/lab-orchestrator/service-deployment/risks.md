# Service deployment — risks

## Scope

### In

- Agent/human deployment workflow, exact releases, systemd user unit, update,
  observation, rollback, secret boundary, and service/worker environment split.

### Out

- OS provisioning, firewall automation, firmware/HIL, distributed deployment,
  database down-migration, and automatic release deletion.

## Assumptions

- Linux host with systemd user services, Git, Python 3.11+, venv/pip, sufficient
  disk, device permissions, and network access required by configured gates.
- One service instance owns the local SQLite state directory.
- The operator can identify an approved exact source SHA and understands which
  unit/config/state paths are live.

## Open questions

- Should a future application command provide an explicit drain state instead
  of relying on observed running assignment count and timing?
- Which future database changes will require backup/restore automation beyond
  retained-code rollback?
- Should releases eventually consume signed wheels instead of source installs?

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Restart races a newly claimed assignment | Cleanup interruption and uncertain device state | Health/log/state changes around stop | Require immediate zero-running recheck, minimize/report the race, and add future drain support |
| Candidate dependency/config failure | Service cannot start | Prepare/validate or systemd journal failure | Block cutover or restore previous link |
| Incompatible DB migration | Old release cannot read state | Migration compatibility review/startup error | Back up and use explicit forward/restore plan |
| Disk fills while preparing release | Candidate incomplete; possible state risk if shared filesystem full | Free-space/install errors | Keep releases bounded and check space first |
| Unit sandbox omits a required write path | Runner/config action fails | Journal permission denial | Add only the exact required external path and reverify |
| Health returns `ok` while loop fails | False confidence | Background exception logs and stale work | Inspect bounded journal and operational state separately |

## Security, privacy, and safety

- Environment and API-token files grant service authority; use mode 0600,
  never print contents, and keep them outside source/releases.
- Unit hardening must not hide missing USB permissions or broaden writable paths.
- Planned updates wait for no active assignment. Forced recovery never asserts
  device cleanup; inspect hardware before retry.

## Performance and resource risks

Side-by-side release venvs consume disk and candidate verification consumes CPU/
network. Bound retained releases, logs, HTTP reads, subprocess waits, and keep
application state storage separate from disposable releases.

## Rollout and rollback

Adopt the unit and release layout first without changing private config/state,
then perform one authorized idle update. Keep the previous release and source
SHA until service/API/log checks and an optional rollback drill pass. Stop and
restore the old link on any unexplained regression.
