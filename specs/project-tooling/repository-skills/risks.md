# Repository skills — risks

## Scope

### In

- Repo-owned skill packaging, discovery metadata, installation links,
  validation, portability, agent guidance, and update behavior.

### Out

- Global agent product configuration, plugin marketplaces, automatic local
  migration, credentials, and live operational authorization.

## Assumptions

- The agent supports SKILL.md packages and optional `agents/openai.yaml`.
- The repository remains available at the link target after installation.
- Users understand that linked installations reflect source edits immediately.

## Open questions

- When would the catalog need versioned copied releases instead of development
  links to one checked-out repository?
- Should a future cross-platform installer support Windows junctions?

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Destination already contains another skill | Data loss if overwritten | Status reports conflict | Refuse and show explicit comparison guidance |
| Repository moves after linking | Installed skill becomes broken | Status resolves link target | Relink only after confirming the new source |
| Trigger description is vague | Skill is missed or invoked incorrectly | Review/usage tests | Name concrete tasks and boundaries in description |
| Skill embeds local values | Privacy leak and non-portability | Validator scan/review | Replace with arguments, XDG paths, or documented examples |
| Skill grants itself authority | Unapproved service/hardware mutation | Instruction review | Explicitly preserve user/AGENTS/spec authorization rules |

## Security, privacy, and safety

Skills are executable operational guidance. Treat changes like code: review
scripts, reject credentials/private coordinates, preserve approval boundaries,
and test mutation helpers only in temporary or explicitly authorized targets.

## Performance and resource risks

Large instructions consume context and overly broad validation wastes time.
Keep SKILL.md concise, load references progressively, bound scans to tracked
skills, and avoid dependency-heavy validators.

## Rollout and rollback

Validate and install into a temporary agent home first. Real installation is an
explicit user action. Roll back a managed skill by reverting repository source
or, with user authorization, unlinking only the confirmed managed destination;
never delete an unmanaged conflict.
