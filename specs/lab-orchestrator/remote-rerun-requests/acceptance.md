# Remote rerun requests — acceptance

## Functional behavior

- [x] **ORCH-RERUN-AC-01:** An active allowlisted Status login can request all
  assignments in an eligible terminal gate or one assignment linked to a child.
- [x] **ORCH-RERUN-AC-02:** Status deduplicates active requests for one gate
  snapshot and stores requester, target, state, attempts, lease, and resolution.
- [x] **ORCH-RERUN-AC-03:** A scoped super-admin lab token atomically claims at
  most one matching repository/gate request; expired claims are recoverable.
- [x] **ORCH-RERUN-AC-04:** The lab rejects public/private identity or state
  mismatches before changing assignments or touching hardware.
- [x] **ORCH-RERUN-AC-05:** Accepted requests atomically record remote identity,
  requeue exactly the requested assignments, and preserve prior attempt evidence.
- [x] **ORCH-RERUN-AC-06:** Redelivery of an already applied request is
  idempotently accepted without a second local transition.

## Interfaces and compatibility

- [x] **ORCH-RERUN-AC-07:** Queue polling is disabled by default and requires a
  dedicated `gates:reruns:consume` token scope for coordinated rollout.
- [x] **ORCH-RERUN-AC-08:** Queue payloads contain only public run identity and
  bounded resolution text, never private lab configuration or credentials.

## Quality attributes

- [ ] **ORCH-RERUN-AC-09:** Tests cover authentication, validation, duplicate
  requests, exclusive claims, lease recovery, mismatch rejection, selected/all
  requeueing, and post-commit resolution retry.
- [ ] **ORCH-RERUN-AC-10:** One live signed-in request has been claimed and run
  by the deployed lab without duplicate execution.

## Verification evidence

- `mining-qa-status`: 29 unit tests, ESLint, TypeScript, and the Next.js
  production build passed on 2026-08-10.
- `mining-qa-lab`: 56 available unit tests passed on 2026-08-10; nine unrelated
  FastAPI-extra tests were skipped because that optional dependency is absent.
  The source distribution/wheel build and repository skill validator passed.
- No live Supabase migration/claim or physical-lab rerun was performed.

## Acceptance rule

Status and lab must deploy compatibly with polling opt-in kept off until the
database migration and scoped token exist. Live completion claims require
inspection of the request, local run, child result, and parent update.
