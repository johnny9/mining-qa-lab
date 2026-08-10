# Configuration and control plane — intent

## Problem

Repositories, gates, test modules, lab inventory, deployment policy, and API
security form one interdependent configuration. Invalid or concurrent edits can
schedule unsafe work or silently discard operator changes.

## Why it matters

Configuration is executable lab policy. It must fail closed, remain reviewable,
and identify the exact snapshot used for each gate.

## Stakeholders

- Lab operators editing resources and gates.
- Maintainers evolving orchestrator schema.
- Gate runs that need immutable policy provenance.

## Desired outcome

One validated schema-versioned YAML document is the human source of truth;
reads expose a revision and writes are checked, backed up, and atomic.

## Primary flow

Load YAML, reject unsafe/invalid values, normalize defaults, compute a digest
and revision, serve the snapshot, then replace or mutate only against the
caller's expected revision.

## Alternate and failure flows

- Invalid YAML/schema returns a bounded configuration error.
- Stale revision rejects a write without changing disk.
- Persistence failure leaves the previous valid file available.

## Non-goals

- Storing secrets in YAML.
- Dynamically rewriting an already-created gate snapshot.
- Acting as a general configuration database.
