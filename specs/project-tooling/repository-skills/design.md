# Repository skills — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Skill catalog | Store installable skills and their resources | `skills/` |
| Skill installer | List/status/install repo-backed links without replacement | `scripts/manage-codex-skills` |
| Skill validator | Check structure, metadata, syntax, links, and portability | `scripts/validate-codex-skills` |
| Agent guidance | Route agents to relevant repo skills and safe update rules | `AGENTS.md` |
| Skill tests | Exercise installation conflicts and repository contracts | `tests/unit/test_repository_skills.py` |

## Interfaces and contracts

### CLI

- `scripts/manage-codex-skills list` lists supported names.
- `scripts/manage-codex-skills status [all|SKILL...]` reports linked, missing,
  or conflicting destinations without mutation.
- `scripts/manage-codex-skills install all|SKILL...` creates only missing links
  under `${CODEX_HOME:-$HOME/.codex}/skills` and returns nonzero on conflict.
- `scripts/validate-codex-skills` validates every tracked skill.

### Configuration

- `CODEX_HOME` optionally selects the agent home. If unset, installation uses
  `$HOME/.codex`; if neither is usable, installation fails explicitly.

### Environment

- Installer reads only `CODEX_HOME`/`HOME`; it does not resolve or store project
  secrets. A skill may describe environment names but never contain live values.

### Python API

- None. Scripts are command-line contracts and skills are Markdown/resource
  packages rather than importable project APIs.

### HTTP or external protocols

- None for installation/validation. A skill may document external protocols
  owned by its feature spec, subject to normal user authorization.

### Files, artifacts, payloads, and persistent state

- `skills/<hyphen-name>/SKILL.md` contains only `name` and `description` in YAML
  frontmatter and concise imperative instructions.
- `agents/openai.yaml` supplies quoted display name, 25–64 character short
  description, and a default prompt explicitly naming `$<skill-name>`.
- Optional `scripts/`, `references/`, and `assets/` contain only resources the
  skill needs. Installed repository-backed links intentionally reflect tracked
  updates immediately.

## Contract constraints

### Required invariants

- Skill directory and frontmatter name match and use lowercase hyphen-case.
- Description states what the skill does and concrete triggers for its use.
- Skill instructions defer to user authorization, AGENTS.md, specs, and live
  evidence; they never turn deployment or HIL into an implicit action.
- Installation is idempotent for the correct link and fail-closed for every
  file, directory, or link conflict.
- Tracked skills contain no private home path, specific private IP/MAC, account
  ID, credential, ignored profile, or live service state.
- Detailed reusable knowledge lives once in directly linked resources rather
  than being duplicated across skill files.

### Forbidden behavior

- Do not overwrite, delete, or silently migrate an installed destination.
- Do not edit a separate installed copy when a repo-backed link is managed.
- Do not add auxiliary README/changelog/install guides inside a skill package.
- Do not claim a skill was installed or exercised against a live system when
  only temporary validation occurred.

## Data and state

The repository skill tree is canonical. Installation state is only the presence
and target of a local link. Project source control owns skill history; the
installer owns no database or hidden manifest.

## Control and data flow

1. Agent/user selects a tracked name and runs validation.
2. Status resolves the destination without following an unrelated object.
3. Install creates a missing link or stops on conflict.
4. Agent discovery loads metadata, then SKILL.md, then only needed resources.
5. Skill updates change tracked source and automatically reach managed links.

## Failure and recovery

- Validation failure blocks installation/handoff until the named file is fixed.
- Destination conflict prints comparison guidance and requires explicit user
  decision; no automatic recovery mutates it.
- Broken managed link is reported as conflict/missing source and repaired only
  after confirming the repository location.

## Compatibility and migration

- Skills follow the current SKILL.md and `agents/openai.yaml` conventions.
  Metadata changes are validated before publication.
- Standalone installed directories migrate by explicit diff/review, removal or
  backup by the user, and then normal linked installation.

## Resource and operational constraints

Skills keep SKILL.md below 500 lines, use progressive disclosure, and avoid
unnecessary resources. Validation is offline, bounded to the tracked skill tree,
and must not contact services or mutate agent installation state.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Service deployment](../../lab-orchestrator/service-deployment/SPEC.md) | First repo-owned operational skill and its authoritative deployment contract. |
| [Configuration and control plane](../../lab-orchestrator/configuration-and-control-plane/SPEC.md) | Skills must use validated public config interfaces rather than edit hidden state. |
| [Lab inventory and preflight](../../lab-orchestrator/lab-inventory-and-preflight/SPEC.md) | Device onboarding separates validated inventory from authorized read-only preflight. |
| [Gate planning and supersession](../../lab-orchestrator/gate-planning-and-supersession/SPEC.md) | Gate creation previews the deterministic matrix without scheduling work. |
| [Persistence, leases, and recovery](../../lab-orchestrator/persistence-leases-and-recovery/SPEC.md) | Deployment skill preserves durable state and fail-closed recovery semantics. |

## Verification approach

Run the standard skill quick validator, repository validator, temporary
CODEX_HOME list/status/install/conflict tests, Python compilation, resource/link
checks, personal-data scan, spec integrity, and whitespace validation.
