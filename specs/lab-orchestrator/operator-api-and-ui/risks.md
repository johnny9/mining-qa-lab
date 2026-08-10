# Operator API and UI — risks

## Scope

### In

- REST/UI/CLI operator surfaces, auth/network policy, and bounded requests.

### Out

- Internet-scale identity/RBAC and external reverse-proxy configuration.

## Assumptions

- Service runs on a restricted lab network under one operator trust domain.
- Proxying preserves a meaningful client address if allowed-network checks apply.

## Open questions

- When will multiple operator roles require identity-aware audit/RBAC?
- Should health gain persisted last-success/error fields for poll and worker loops?

## Failure modes

- Misconfigured bind/proxy makes a control surface public.
- Token file permissions or logs leak bearer authority.
- Stale UI submits a destructive config edit without correct revision.
- Health says `ok` while the background loop is repeatedly failing.
- A forged database path or oversized/binary inline view exposes unrelated host
  data or exhausts the API process.

## Security, privacy, and safety

Default to bearer auth and loopback/restricted networks. Mutations are explicit,
conditional, and bounded; sensitive lab coordinates/photos remain restricted.
Archived artifacts receive the same authentication and restricted-network
treatment and storage paths are never returned to clients.

## Performance and resource risks

Slow probes or excessive requests can starve the event loop; use thread offload,
timeouts, request caps, and deployment-level rate/network controls.

## Rollout and rollback

Validate locally, bind loopback first, audit auth/network behavior, then expose
only as needed. Roll back to loopback/stop service while durable state remains.
