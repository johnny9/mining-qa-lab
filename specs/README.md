# Specifications

Specifications preserve durable intent: what the system must do, who or what
depends on it, why the behavior matters, how success is verified, and which
constraints must remain true.

They complement rather than replace source code, tests, generated OpenAPI,
operator documentation, and temporary delivery plans.

## Repository-level documents

- [OVERVIEW.md](OVERVIEW.md): purpose, ownership boundary, actors, capabilities,
  and system context.
- [INDEX.md](INDEX.md): complete directory of feature specs. Every feature
  `SPEC.md` must be listed exactly once.
- [STORY-MAP.md](STORY-MAP.md): outcome-oriented navigation across features.
- [MAINTENANCE.md](MAINTENANCE.md): deterministic coherence and reconciliation
  checks.
- `reviews/`: confirmed product and architecture review records.
- `_template/`: copyable feature-spec template.

## Feature layout

```text
specs/<area>/<feature>/
  SPEC.md
  intent.md
  acceptance.md
  design.md
  risks.md
```

`SPEC.md` is the canonical feature entry, lifecycle record, and changelog.
Companion files separate stakeholder intent, executable acceptance, durable
design contracts, and risks so that each stays readable.

Feature directories are domain slices, not mirrors of source directories. A
slice may cross persistence, API, service, worker-process, and test modules when
those pieces jointly deliver one lab outcome. Detailed runner features remain
in the separate `mining-qa-testcode` specification tree; this repository links
them as external contracts instead of duplicating them.

Additional focused references are allowed when they define a real contract or
reduce noise. Link them from `SPEC.md` or `design.md` and say whether they are
normative or explanatory.

## Lifecycle

For new features and significant behavior or architecture changes:

1. Search [INDEX.md](INDEX.md) for an existing feature.
2. Draft `intent.md` and independently verifiable `acceptance.md` before
   implementation.
3. Register the feature in the index in the same change.
4. Implement against the acceptance criteria.
5. Reconcile `design.md`, `risks.md`, and acceptance evidence with the actual
   result.
6. Update lifecycle and last-reconciled metadata in `SPEC.md`.
7. Append a dated changelog entry.
8. Refresh the overview or story map when the project-level picture changed.

For smaller observable fixes, implementation may precede the documentation
edit, but the affected feature must be reconciled before the change is done.

Purely internal work does not require a spec update unless it changes a
documented interface, constraint, supported environment, operating procedure,
safety property, recovery behavior, or user-visible result.

## Status and evidence

- `Lifecycle` is one of `proposed`, `implementing`, `supported`, `deprecated`,
  or `retired`.
- `Last reconciled` records the date the spec was last compared with current
  implementation evidence.
- `[x]` in `acceptance.md` means the criterion has current recorded evidence.
  It is not a guess based on a class name or historical intention.
- Evidence may be automated tests, static analysis, protocol traces, package
  builds, live service checks, measurements, simulations, or explicit HIL.
- Historical HIL can inform intent and risk, but it is labeled historical and
  is not presented as current verification.
- Criteria remain unchecked when evidence is missing, stale, or inconclusive.

## API documentation rule

Each design file names every applicable surface:

- CLI arguments and exit statuses
- TOML/YAML configuration
- environment variables
- Python extension contracts
- HTTP endpoints and authorization
- external protocols
- files, artifacts, payloads, and persistent state

Use `none` when a category does not apply. Generated `/openapi.json` remains
the exact REST shape source; specs define ownership, semantics, invariants, and
failure behavior rather than copying generated schemas field for field.

## Reviews

Store review records under `specs/reviews/` using:

```text
YYYY-MM-DD-<product|architecture>-<feature-slug>-review.md
```

Use `specs/reviews/TEMPLATE.md`. Apply a review only after its decision and
required file changes are confirmed. Select reviews by feature slug before
choosing the latest matching record.
