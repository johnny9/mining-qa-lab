# Agent instructions

## Project mission

`miner-testcode` contains two related products:

- `miner-test` runs detailed, failure-safe tests against mining hardware and
  publishes child results and evidence.
- `miner-orchestrator` converts authorized repository events and operator
  requests into durable lab gates, executes `miner-test`, and publishes only
  parent gate aggregation and child-result links.

Read [specs/OVERVIEW.md](specs/OVERVIEW.md) for the complete ownership boundary
and [specs/INDEX.md](specs/INDEX.md) for feature-level contracts.

## Working behavior

- State material assumptions and resolve ambiguity before changing public
  behavior, compatibility, safety, data, hardware state, or interfaces.
- Prefer the smallest coherent change that satisfies the request.
- Preserve unrelated work and follow the repository's established structure.
- For defects, establish evidence of the problem before fixing it and add a
  regression that fails before the fix when practical.
- For refactors, establish relevant behavior before and after the change.
- For multi-step work, maintain a short plan with an explicit verification
  step.
- Do not claim a test, build, simulation, deployment, or hardware validation
  that was not actually run.

## Documentation contract

For any non-trivial task:

1. Find the relevant feature through `specs/INDEX.md`.
2. Read its `SPEC.md` and all linked companion files before planning or
   modifying implementation.
3. Read directly related feature specs named in `design.md`.
4. Treat specs as durable intent and code, tests, measurements, and live
   checks as implementation evidence.
5. Report contradictions rather than silently choosing one source.
6. Update specs in the same change when observable behavior, an interface, a
   constraint, an operating procedure, or a durable design decision changes.

Use the project-local `.agents/skills/specs/SKILL.md` workflow for new features,
feature reconciliation, review preparation, and product or architecture
reviews.

## Repository skills

Installable project skills live under `skills/` and remain the source of truth;
do not maintain a separately edited copy under an agent home.

- Read [Repository skills](specs/project-tooling/repository-skills/SPEC.md) for
  the packaging and installation contract.
- For orchestrator service installation, inspection, update, restart, rollback,
  or systemd troubleshooting, use
  `skills/manage-lab-orchestrator-deployment/SKILL.md` and read
  [Service deployment](specs/lab-orchestrator/service-deployment/SPEC.md).
- Validate changes with `./scripts/validate-codex-skills`.
- Check destinations with `./scripts/manage-codex-skills status SKILL...`, then
  install with `./scripts/manage-codex-skills install SKILL...`.
- The installer creates repository-backed links and never replaces an existing
  file, directory, or different link. Compare conflicts before asking whether
  to migrate them.
- A skill supplies procedure, not authority. Service mutation, config changes,
  HIL, firmware deployment, and publication still require the relevant request.

A documentation update is normally unnecessary for formatting, test-only
cleanup, internal renames, or behavior-preserving refactors unless they alter a
documented contract, supported environment, safety property, or verification
procedure.

When creating a feature spec, add it to `specs/INDEX.md` in the same change.
Update `specs/OVERVIEW.md` or `specs/STORY-MAP.md` when the project-level
capability or actor flow changes. Temporary delivery notes belong in `plans/`,
not in the durable specification tree.

## Source-of-truth order

- `README.md`: installation, common commands, and operator orientation.
- `specs/OVERVIEW.md`: system purpose, ownership boundary, actors, and major
  capabilities.
- `specs/INDEX.md`: complete directory of feature specs.
- `specs/<area>/<feature>/SPEC.md`: canonical feature entry, lifecycle, and
  changelog.
- Feature companion files: intent, acceptance, design, and risks.
- `plans/`: temporary delivery material; never the only durable record of a
  decision or supported behavior.
- Code and tests: current implementation evidence that must be reconciled with
  documented intent.

If these sources conflict, stop and report the conflict. Resolve it in the same
change when that resolution is within scope.

## Non-negotiable system boundaries

- `miner-test` owns test discovery, device lifecycle, mutable-state cleanup,
  detailed evidence, privacy, provenance, and child-result publication.
- `miner-orchestrator` owns event trust, gate planning, durable state, lab
  leases, optional firmware deployment, worker execution, parent gate
  publication, and child-result linking.
- The orchestrator must not duplicate detailed child publication or upload
  child artifacts itself.
- Mining QA Status is an external collector and presentation service. It does
  not receive lab device credentials or control hardware.
- Devices execute on the host that owns their USB and private lab coordinates.

## Hardware, security, and privacy safety

- Hardware writes require an explicit non-read-only configuration and a valid,
  captured cleanup baseline.
- Cleanup failures are test errors and must never be hidden by a passing test
  body.
- Never write redaction markers, masked passwords, unresolved environment
  placeholders, or artifact-derived values to a device.
- Preserve rollback paths. Verify original mutable state after a test that
  changes pool, pause, or other device settings.
- Secrets are supplied through named environment variables. Do not serialize
  resolved secrets into TOML, YAML, logs, artifacts, metadata, subprocess
  arguments, or published results.
- Bound every network response, serial input, uploaded artifact, and metadata
  field. Safe reads may retry as documented; writes must not be retried unless
  the protocol proves idempotence.
- Firmware deployment requires an immutable source commit, successful matching
  build, verified archive digest and member, expected board identity, bounded
  upload, post-reboot identity check, and fail-closed deployment marker.
- Untrusted pull requests require approval of one exact freshly revalidated
  head SHA. Do not broaden that approval to a contributor or future commit.
- First observation of a repository source establishes a cursor baseline and
  must not unexpectedly schedule hardware.
- A newer PR head may supersede queued work but must never interrupt an active
  assignment before device cleanup.
- SSH worker execution must keep agent forwarding disabled and pass only the
  allowlisted environment.

## Project commands

Use the repository virtual environment when present. Do not invent or claim
formatters, linters, or hardware commands that the repository does not define.

| Purpose | Command |
|---|---|
| Install runner and orchestrator | `.venv/bin/python -m pip install -e '.[orchestrator]'` |
| Full unit tests | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v` |
| One unit module | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.<module> -v` |
| Build wheel and sdist | `python3 -m build --no-isolation` |
| Validate orchestrator config | `.venv/bin/miner-orchestrator --config <local-yaml> validate` |
| Run hardware tests | `.venv/bin/miner-test --config <local-toml>` |
| Documentation integrity | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v` |
| Validate repository skills | `./scripts/validate-codex-skills` |
| Inspect skill installation | `./scripts/manage-codex-skills status all` |
| Whitespace validation | `git diff --check` |

Hardware commands require a user-authorized target and local ignored profile.
Before HIL, re-check live device identity, firmware source, pool, serial path,
read-only state, and publication destination. After HIL, verify cleanup and
healthy mining independently.

## Verification expectations by change

| Change | Minimum evidence |
|---|---|
| Runner/config/test selection | Focused tests, full unit suite, package build |
| Device lifecycle or write path | Fake-device regression, negative safety case, cleanup assertion, full unit suite |
| Interface or protocol | Boundary/error tests, bounded-input behavior, full unit suite |
| Privacy/provenance/publishing | Redaction and provenance tests, payload assertions, full unit suite |
| Orchestrator config/API | Validation, auth/network/ETag tests, full unit suite |
| Events/planning/database | Idempotence, trust, supersession, lease/recovery tests, full unit suite |
| Firmware deployment | Exact-SHA/digest/member/board/reboot/failure tests; HIL only when authorized |
| Repository skill or service deployment | Skill/install/inspector/unit tests, spec integrity, package build; live service only when authorized |
| Documentation only | Spec integrity test, maintenance checklist, `git diff --check` |

## Repository hygiene

- Never commit local TOML/YAML profiles, service wrappers, API tokens, device
  coordinates, photos, run artifacts, firmware caches, or generated package
  output.
- Inspect staged and unstaged changes separately. Stage only files belonging to
  the requested work.
- Commit and push only when explicitly authorized. Preserve remote work and
  verify the exact remote SHA after publication.
- Keep feature changes, tests, specs, examples, and user documentation
  synchronized.

## Definition of done

- Requested behavior is implemented or the requested analysis is complete.
- Relevant verification passed, or limitations are reported precisely.
- Public behavior and important constraints match the specs.
- New feature specs are indexed exactly once.
- Acceptance evidence, lifecycle, last-reconciled date, and changelog are
  current.
- Temporary decisions that became durable were moved from `plans/` into the
  appropriate feature spec.
- `specs/MAINTENANCE.md` has been applied for spec-worthy work.
- Unrelated files remain untouched.
