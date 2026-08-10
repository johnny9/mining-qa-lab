# Operator API and UI — intent

## Problem

Operators need to inspect and control a long-running lab service without editing
SQLite, bypassing validation, or using ambiguous commands for trust-sensitive work.

## Why it matters

The control surface can revise executable policy, approve untrusted code, probe
private devices, and schedule physical work. Its security and concurrency
contracts must be clearer than its presentation.

## Stakeholders

- Local lab operators.
- Automation using documented REST/OpenAPI.
- Maintainers diagnosing service/configuration state.

## Desired outcome

A versioned REST API and small server-rendered UI expose safe observability and
explicit authenticated mutations, with conditional configuration writes and
exact source identities. Operators can run a gate against a selected project,
source, and device types and inspect privately archived results without leaving
the lab UI.

## Primary flow

Authenticate/restrict the client, read current config/gates/lab/history, validate
or conditionally mutate resources, approve/trigger exact work, and observe runs
and probes through bounded responses.

## Alternate and failure flows

- Bearer failure returns unauthorized; disallowed network returns forbidden.
- Authentication-free mode is allowed only with nonempty allowed networks.
- Stale config mutations return precondition failure.

## Non-goals

- Public multi-tenant SaaS administration.
- Browser-side ownership of orchestration truth.
- Reporting background-loop health beyond explicitly measured API fields.
