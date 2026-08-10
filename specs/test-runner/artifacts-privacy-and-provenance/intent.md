# Artifacts, privacy, and provenance — intent

## Problem

Hardware failures need rich logs and telemetry, but raw evidence can expose
pool payout identity, credentials, device addresses, serial paths, or results
that cannot be tied to the code that actually ran.

## Why it matters

Unsafe evidence harms operators; unattributable evidence harms engineering.
Both make remotely published test results untrustworthy.

## Stakeholders

- Lab operators responsible for devices and credentials.
- Developers debugging child results.
- Reviewers relying on source and artifact provenance.

## Desired outcome

Every run has a bounded, structured artifact tree with stable public labels,
sanitized content, and exact source provenance suitable for local inspection or
authorized publication.

## Primary flow

Create run/test artifact scopes, capture structured evidence through privacy
formatters, record provenance, finalize immutable result files, and hand only
sanitized paths/payloads to publishers.

## Alternate and failure flows

- A redaction/sanitization failure prevents remote publication.
- Missing or inconsistent source provenance is visible and can fail strict
  publication policy.
- Artifact-write failures are reported as test infrastructure failures.

## Non-goals

- Guaranteeing secrecy for arbitrary third-party text after it bypasses the
  evidence APIs.
- Replacing host access control or publisher authentication.
- Treating human-readable labels as globally unique hardware identity.
