# Artifact resolution and deployment — risks

## Scope

### In

- Exact artifact resolution, secure cache/extraction, OTA, verify, and marker.

### Out

- Firmware build correctness and automatic serial unbrick recovery.

## Assumptions

- Workflow head SHA and artifact metadata are trustworthy when authenticated.
- Target exposes sufficient board/version identity before and after OTA.

## Open questions

- Which future boards require manufacturer/factory image handling instead of OTA?

## Failure modes

- Wrong/stale workflow artifact is selected.
- ZIP traversal or oversized content attacks the host.
- Power/network loss interrupts OTA.
- Weak identity check accepts an incompatible board or old firmware.

## Security, privacy, and safety

Treat downloaded archives as hostile, minimize token scope, strip auth on
redirect, verify digests/board, and preserve an operator recovery route.

## Performance and resource risks

Artifact waits/downloads can consume time/disk/API quota; cache content safely
and enforce time, size, and polling bounds.

## Rollout and rollback

Introduce new targets with manual non-required gates and verified recovery.
Rollback uses the documented known-good image/path, never an unverified cache.
