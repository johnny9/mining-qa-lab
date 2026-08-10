# Agent instructions

## Project mission

`mining-qa-lab` is the lab-control and gate-orchestration repository in the
Mining QA family. It owns trusted event intake, durable gate planning, lab
inventory and leases, optional firmware deployment, installation and execution
of external testcode, operator controls, and parent gate publication.

The detailed runner and hardware tests live in
[`mining-qa-testcode`](https://github.com/johnny9/mining-qa-testcode). Mining QA
Status is an external collector and presentation service. Start with
[specs/OVERVIEW.md](specs/OVERVIEW.md), then use
[specs/INDEX.md](specs/INDEX.md) to locate the feature being changed.

## Working behavior

- Inspect current code, tests, configuration contracts, and relevant specs
  before proposing or changing behavior.
- State material assumptions before changing a public interface, safety rule,
  persistent state, compatibility promise, or hardware behavior.
- Prefer the smallest coherent change and preserve unrelated work.
- For a defect, establish evidence and add a regression that fails before the
  fix when practical.
- Keep a short plan for multi-step work and include an explicit verification
  step.
- Never claim a test, build, service check, simulation, deployment, or HIL run
  that was not actually performed.

## Specification workflow

For non-trivial work:

1. Find the feature in `specs/INDEX.md`.
2. Read its `SPEC.md`, `intent.md`, `acceptance.md`, `design.md`, and `risks.md`.
3. Read directly related slices named in `design.md`.
4. Treat specs as durable intent and code/tests/live checks as implementation
   evidence. Report contradictions instead of silently choosing one.
5. Update the spec in the same change when behavior, API, payload, schema,
   state, constraints, operating procedure, or durable design changes.
6. Add new features to the index exactly once and update the overview or story
   map when the project-level flow changes.

Use [.agents/skills/specs/SKILL.md](.agents/skills/specs/SKILL.md) for new
features, reconciliation, and product or architecture reviews. Temporary
delivery notes belong in `plans/`, never as the only record of a durable
decision.

## Repository skills

Installable project skills live under `skills/` and are governed by
[Repository skills](specs/project-tooling/repository-skills/SPEC.md).

- For service inspection, installation, update, restart, rollback, or systemd
  diagnosis, read
  `skills/manage-lab-orchestrator-deployment/SKILL.md` and
  [Service deployment](specs/lab-orchestrator/service-deployment/SPEC.md).
- Validate skills with `./scripts/validate-codex-skills`.
- Inspect installation with `./scripts/manage-codex-skills status all` and
  install only when requested with `./scripts/manage-codex-skills install ...`.
- A skill supplies procedure, not authority. It does not authorize service
  mutation, private config changes, firmware deployment, HIL, or publication.

## Source-of-truth order

- `README.md`: installation, commands, operator orientation, and relationships.
- `contracts/orchestration-v1.md`: versioned lab/testcode process boundary.
- `specs/OVERVIEW.md`: purpose, ownership, actors, and system context.
- `specs/INDEX.md`: complete feature directory.
- `specs/<area>/<feature>/SPEC.md` and companions: feature intent,
  acceptance, design, risks, lifecycle, and changelog.
- Generated `/openapi.json`: exact REST field shape.
- Code and tests: current implementation evidence to reconcile with intent.

Stop and report a conflict between these sources. Resolve it in the same change
when the resolution is in scope.

## Non-negotiable boundaries

- The orchestrator owns authorization, planning, durable state, exclusive lab
  leases, optional verified firmware deployment, runner installation/process
  execution, parent gate publication, and child-result linking.
- `mining-qa-testcode` owns test discovery, hardware lifecycle, mutable-state
  cleanup, detailed evidence, privacy, source provenance, result-pointer
  writing, and child-result publication.
- Do not copy runner modules or hardware test cases into this repository. Do not
  reconstruct or upload detailed child results in the orchestrator.
- Change the cross-repository process contract only through a versioned,
  coordinated reader/writer migration. Compatible readers ship before a new
  field becomes required.
- Mining QA Status never receives private device credentials and does not
  control lab hardware.

## Hardware, trust, and privacy safety

- First observation of a source establishes a cursor baseline; it must not
  unexpectedly schedule historical hardware work.
- Untrusted pull requests require approval for one exact, freshly revalidated
  head SHA. Never broaden approval to a contributor or later commit.
- A new PR head may supersede queued work but must not interrupt an active
  assignment before runner cleanup.
- Acquire all device leases before testcode installation, firmware deployment,
  or execution; release them on every terminal path.
- Firmware deployment requires immutable source/build provenance, verified
  archive digest/member, expected board identity, bounded upload, post-reboot
  verification, and fail-closed markers.
- Secrets come from named environment variables. Never serialize resolved
  secrets into YAML, logs, metadata, state, subprocess arguments, or results.
- Bound every network response, artifact, worker log, result pointer, and
  metadata field. Do not retry non-idempotent writes without protocol proof.
- SSH execution disables agent forwarding and passes only the allowlisted
  environment plus the explicit runner contract.
- Service restart or lease release is not proof of physical device cleanup.

## Project commands

Use the repository virtual environment when present.

| Purpose | Command |
|---|---|
| Install service | `.venv/bin/python -m pip install -e .` |
| Full unit tests | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v` |
| One unit module | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.<module> -v` |
| Spec integrity | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v` |
| Build wheel and sdist | `python3 -m build --no-isolation` |
| Validate config | `.venv/bin/miner-orchestrator --config <local-yaml> validate` |
| Validate skills | `./scripts/validate-codex-skills` |
| Inspect skill installation | `./scripts/manage-codex-skills status all` |
| Whitespace | `git diff --check` |

Do not invent a formatter, linter, hardware command, or service path that the
repository does not define.

## Verification expectations

| Change | Minimum evidence |
|---|---|
| Config/API/UI | validation plus auth, network, ETag, error, and unit tests |
| Events/planning/database | idempotence, trust, supersession, lease, recovery, and unit tests |
| Testcode bootstrap/process contract | exact-SHA, dirty/wrong-origin, ordering, bounded pointer, local/SSH, and unit tests |
| Firmware deployment | SHA/digest/member/board/reboot/failure tests; HIL only when authorized |
| Service deployment or skill | inspector/installer/unit/spec/skill checks and package build; live service only when authorized |
| Documentation only | spec integrity, maintenance checklist, and `git diff --check` |

## Repository hygiene and done criteria

- Never commit private YAML, service overrides, device coordinates, tokens,
  photos, SQLite state, job output, firmware caches, worker checkouts, virtual
  environments, or generated packages.
- Inspect staged and unstaged changes separately and stage only in-scope files.
- Commit and push only when explicitly authorized; preserve remote work and
  verify the exact remote SHA.
- Work is done when requested behavior is implemented, specs and tests agree,
  acceptance evidence is current, relevant verification has passed (or limits
  are precise), the maintenance checklist was applied, and unrelated files are
  untouched.
