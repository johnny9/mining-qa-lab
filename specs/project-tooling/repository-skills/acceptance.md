# Repository skills — acceptance

## Functional behavior

- [x] **TOOL-SKILLS-AC-01:** Every catalog skill has valid SKILL.md trigger
  metadata, matching directory name, UI metadata, and only directly useful resources.
- [x] **TOOL-SKILLS-AC-02:** List and status are read-only; install creates a
  repository-backed link only when the destination is absent.
- [x] **TOOL-SKILLS-AC-03:** Correct existing links are idempotent, while files,
  directories, foreign links, and broken links are reported and never replaced.
- [x] **TOOL-SKILLS-AC-04:** Updating tracked skill source updates a managed
  installation without maintaining a second edited copy.

## Interfaces and compatibility

- [x] **TOOL-SKILLS-AC-05:** `CODEX_HOME` and `$HOME/.codex` selection is
  deterministic, documented, and fails clearly when neither base is available.
- [x] **TOOL-SKILLS-AC-06:** AGENTS.md and human documentation identify the
  catalog, validator, install/status commands, source-of-truth rule, and relevant specs.

## Quality attributes

- [x] **TOOL-SKILLS-AC-07:** Validation catches malformed metadata, missing
  resources/UI data, Python syntax, unresolved internal links, and common
  personal/machine-identifying values without contacting external systems.
- [x] **TOOL-SKILLS-AC-08:** Unit tests exercise a temporary agent home for
  install, idempotence, conflict refusal, and status without changing the real home.
- [x] **TOOL-SKILLS-AC-09:** Each skill passes the standard quick validator plus
  repository spec, package, unit, privacy, and whitespace checks appropriate to its files.

## Verification evidence

- 2026-08-10: The standalone lab's 48-test unit suite passed, including temporary
  `CODEX_HOME` list/status/install/idempotence, unmanaged/foreign/broken-link
  refusal, and repository validation tests.
- 2026-08-10: The repository validator, standard skill quick validator, Python
  and shell syntax checks, specification integrity, wheel/sdist build, privacy
  scan, and `git diff --check` passed.
- Installation into the real agent home was not requested or performed; the
  evidence uses only temporary installation targets.

## Acceptance rule

A skill is acceptable only when its trigger, instructions, resources, install
path, validation, spec relationships, and safety boundaries have current
evidence. Conflicting or personally identifying content blocks publication.
