# Repository skills — intent

## Problem

Important project workflows can live only in conversation history or in one
developer's private agent configuration. New agents then rediscover fragile
deployment and safety steps, while copied local skills drift away from reviewed
repository guidance.

## Why it matters

Project-specific operational knowledge should be reviewable beside the code it
controls, easy to install, and updated from one source without overwriting a
user's unrelated local skill.

## Stakeholders

- Agents performing repository or lab operations.
- Maintainers reviewing workflow and safety changes.
- Humans installing skills into their agent environment.
- Operators whose local paths, credentials, services, and devices must remain private.

## Desired outcome

Each supported skill has valid trigger metadata, concise instructions, only the
resources it needs, safe installation/status commands, automated validation,
and a durable feature spec. Repository agent guidance points to the catalog and
explains how updates propagate.

## Primary flow

1. Discover a relevant tracked skill through agent guidance or its metadata.
2. Validate it and inspect the destination for conflicts.
3. Install a repository-backed link, use the skill under normal authorization
   rules, and update the tracked source through reviewable repository changes.

## Alternate and failure flows

- An existing destination is reported as a conflict and never replaced.
- Invalid metadata, missing resources, Python syntax errors, broken links, or
  personal/machine-specific values fail validation.
- A copied/unmanaged installation requires explicit comparison and migration.

## Non-goals

- Automatically enabling every repository skill for every user.
- Letting skill instructions broaden user authorization or bypass AGENTS.md.
- Storing credentials, private lab configuration, or live deployment state.
- Creating a separate plugin or marketplace package for one local project skill.
