from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


SCHEMA = """
pragma journal_mode = WAL;
pragma foreign_keys = ON;

create table if not exists source_cursors (
    source_key text primary key,
    value text not null,
    etag text,
    updated_at real not null
);

create table if not exists events (
    id text primary key,
    event_key text not null unique,
    repository_id text not null,
    trigger_type text not null,
    commit_sha text not null,
    branch text,
    pr_number integer,
    pr_url text,
    contributor text,
    changed_paths text not null default '[]',
    payload text not null default '{}',
    created_at real not null,
    planned_at real
);

create table if not exists gate_runs (
    id text primary key,
    gate_id text not null,
    event_id text not null references events(id),
    repository_id text not null,
    commit_sha text not null,
    branch text,
    pr_number integer,
    trigger_type text not null,
    definition_digest text not null,
    config_snapshot text not null,
    status text not null,
    required_policy text not null default 'all',
    qa_result_id text,
    qa_result_url text,
    summary text,
    created_at real not null,
    started_at real,
    finished_at real,
    unique(gate_id, event_id, definition_digest)
);

create table if not exists assignments (
    id text primary key,
    gate_run_id text not null references gate_runs(id) on delete cascade,
    setup_id text not null,
    module_id text not null,
    platform_key text not null,
    status text not null,
    attempt integer not null default 0,
    result_pointer text,
    qa_result_id text,
    qa_result_url text,
    detail text,
    created_at real not null,
    started_at real,
    finished_at real,
    unique(gate_run_id, setup_id, module_id)
);

create table if not exists assignment_attempts (
    attempt_id text primary key,
    assignment_id text not null references assignments(id) on delete cascade,
    attempt integer not null check(attempt > 0),
    status text not null,
    detail text,
    result_pointer text,
    qa_result_id text,
    qa_result_url text,
    started_at real not null,
    finished_at real,
    unique(assignment_id, attempt)
);

create table if not exists resource_leases (
    resource_id text primary key,
    assignment_id text not null references assignments(id) on delete cascade,
    acquired_at real not null
);

create table if not exists assignment_artifacts (
    id text primary key,
    assignment_id text not null references assignments(id) on delete cascade,
    attempt integer not null,
    relative_path text not null,
    size_bytes integer not null,
    sha256 text not null,
    media_type text not null,
    storage_path text not null,
    created_at real not null,
    unique(assignment_id, attempt, relative_path)
);

create table if not exists publications (
    gate_run_id text primary key references gate_runs(id) on delete cascade,
    status text not null,
    attempts integer not null default 0,
    last_error text,
    updated_at real not null
);

create table if not exists remote_rerun_requests (
    request_id text primary key,
    public_gate_run_id text not null,
    local_gate_run_id text not null references gate_runs(id) on delete cascade,
    mode text not null,
    assignment_ids text not null,
    applied_at real not null
);

create table if not exists central_executions (
    lab_execution_id text primary key,
    central_gate_run_id text not null,
    lab_id text not null,
    definition_digest text not null,
    offer_json text not null,
    state text not null,
    claim_id text,
    claim_generation integer,
    claim_token text,
    claim_expires_at text,
    assignment_id text,
    created_at real not null,
    updated_at real not null,
    unique(central_gate_run_id, lab_id)
);

create table if not exists central_attempts (
    attempt_id text primary key,
    lab_execution_id text not null references central_executions(lab_execution_id),
    assignment_id text not null,
    attempt integer not null,
    state text not null,
    started_at text not null,
    completed_at text,
    pointer_json text,
    cleanup_disposition text,
    unique(lab_execution_id, attempt)
);

create table if not exists central_resource_leases (
    resource_id text primary key,
    lab_execution_id text not null references central_executions(lab_execution_id) on delete cascade,
    assignment_id text not null,
    acquired_at real not null
);

create table if not exists central_agent_control (
    singleton integer primary key check(singleton = 1),
    paused integer not null default 0 check(paused in (0, 1)),
    consecutive_failures integer not null default 0 check(consecutive_failures >= 0),
    last_error text,
    last_cycle_at real,
    next_retry_at real,
    updated_at real not null
);

create table if not exists central_outbox (
    lab_execution_id text primary key references central_executions(lab_execution_id),
    idempotency_key text not null unique,
    body_json text not null,
    state text not null,
    response_code integer,
    updated_at real not null
);

create index if not exists events_unplanned_idx on events(planned_at, created_at);
create index if not exists gate_runs_status_idx on gate_runs(status, created_at);
create index if not exists assignments_status_idx on assignments(status, created_at);
create index if not exists assignment_attempts_assignment_idx
    on assignment_attempts(assignment_id, attempt);
create index if not exists assignment_artifacts_assignment_idx
    on assignment_artifacts(assignment_id, attempt, relative_path);
create index if not exists remote_rerun_requests_run_idx
    on remote_rerun_requests(local_gate_run_id, applied_at);
create index if not exists central_executions_state_idx
    on central_executions(lab_id, state, created_at);

create trigger if not exists assignment_attempts_terminal_immutable
before update on assignment_attempts
when old.finished_at is not null
begin
    select raise(abort, 'terminal assignment attempts are immutable');
end;

create trigger if not exists central_attempts_terminal_immutable
before update on central_attempts
when old.completed_at is not null
begin
    select raise(abort, 'terminal central attempts are immutable');
end;
"""


class OrchestratorDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._connection.executescript(SCHEMA)
        self._migrate_central_attempt_identity()
        self._backfill_assignment_attempts()
        with self.transaction() as connection:
            connection.execute(
                """
                insert into central_agent_control(singleton, updated_at)
                values (1, ?)
                on conflict(singleton) do nothing
                """,
                (time.time(),),
            )
        self.path.chmod(0o600)

    def _migrate_central_attempt_identity(self) -> None:
        row = self._connection.execute(
            "select sql from sqlite_master where type = 'table' and name = 'central_attempts'"
        ).fetchone()
        if not row or "assignment_id text not null unique" not in row["sql"].lower():
            return
        self._connection.executescript(
            """
            alter table central_attempts rename to central_attempts_legacy;
            create table central_attempts (
                attempt_id text primary key,
                lab_execution_id text not null references central_executions(lab_execution_id),
                assignment_id text not null,
                attempt integer not null,
                state text not null,
                started_at text not null,
                completed_at text,
                pointer_json text,
                cleanup_disposition text,
                unique(lab_execution_id, attempt)
            );
            insert into central_attempts select * from central_attempts_legacy;
            drop table central_attempts_legacy;
            create trigger central_attempts_terminal_immutable
            before update on central_attempts
            when old.completed_at is not null
            begin
                select raise(abort, 'terminal central attempts are immutable');
            end;
            """
        )

    def _backfill_assignment_attempts(self) -> None:
        """Preserve evidence created by databases predating normalized attempts."""
        with self.transaction() as connection:
            rows = connection.execute(
                "select * from assignments where attempt > 0"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    insert into assignment_attempts(
                        attempt_id, assignment_id, attempt, status, detail,
                        result_pointer, qa_result_id, qa_result_url, started_at,
                        finished_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    on conflict(assignment_id, attempt) do nothing
                    """,
                    (
                        f"legacy-{row['id']}-{row['attempt']}",
                        row["id"],
                        row["attempt"],
                        row["status"],
                        row["detail"],
                        row["result_pointer"],
                        row["qa_result_id"],
                        row["qa_result_url"],
                        row["started_at"] or row["created_at"],
                        row["finished_at"],
                    ),
                )

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            try:
                self._connection.execute("begin immediate")
                yield self._connection
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def cursor(self, source_key: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "select * from source_cursors where source_key = ?", (source_key,)
        ).fetchone()
        return dict(row) if row else None

    def set_cursor(self, source_key: str, value: str, etag: str | None = None) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                insert into source_cursors(source_key, value, etag, updated_at)
                values (?, ?, ?, ?)
                on conflict(source_key) do update set
                    value = excluded.value,
                    etag = excluded.etag,
                    updated_at = excluded.updated_at
                """,
                (source_key, value, etag, time.time()),
            )

    def persist_central_page(
        self,
        *,
        lab_id: str,
        cursor: str,
        offers: list[Mapping[str, Any]],
    ) -> None:
        """Persist validated/rejected offers and the delivery cursor atomically."""

        now = time.time()
        with self.transaction() as connection:
            for offer in offers:
                execution_id = str(offer["lab_execution_id"])
                connection.execute(
                    """
                    insert into central_executions(
                        lab_execution_id, central_gate_run_id, lab_id,
                        definition_digest, offer_json, state, created_at, updated_at
                    ) values (?, ?, ?, ?, ?, 'received', ?, ?)
                    on conflict(lab_execution_id) do nothing
                    """,
                    (
                        execution_id,
                        str(offer.get("central_gate_run_id", "invalid"))[:128],
                        lab_id,
                        str(offer.get("definition_digest", "0" * 64))[:64],
                        json.dumps(dict(offer), sort_keys=True, separators=(",", ":"))[:65536],
                        now,
                        now,
                    ),
                )
            connection.execute(
                """
                insert into source_cursors(source_key, value, etag, updated_at)
                values (?, ?, null, ?)
                on conflict(source_key) do update set
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (f"central:{lab_id}", cursor, now),
            )

    def central_execution(self, execution_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "select * from central_executions where lab_execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["offer"] = json.loads(value.pop("offer_json"))
        return value

    def pending_central_executions(self, lab_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            """
            select * from central_executions
            where lab_id = ? and state in ('received', 'claimed')
            order by created_at, lab_execution_id
            """,
            (lab_id,),
        ).fetchall()
        values: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            value["offer"] = json.loads(value.pop("offer_json"))
            values.append(value)
        return values

    def update_central_execution(self, execution_id: str, **changes: Any) -> None:
        allowed = {
            "state",
            "claim_id",
            "claim_generation",
            "claim_token",
            "claim_expires_at",
            "assignment_id",
        }
        invalid = set(changes) - allowed
        if invalid:
            raise ValueError(f"unsupported central execution fields: {sorted(invalid)}")
        if not changes:
            return
        columns = ", ".join(f"{key} = ?" for key in changes)
        with self.transaction() as connection:
            connection.execute(
                f"update central_executions set {columns}, updated_at = ? where lab_execution_id = ?",
                (*changes.values(), time.time(), execution_id),
            )

    def start_central_attempt(
        self,
        *,
        execution_id: str,
        assignment_id: str,
        attempt_id: str,
        started_at: str,
        max_attempts: int = 3,
    ) -> tuple[dict[str, Any], bool]:
        with self.transaction() as connection:
            existing = connection.execute(
                "select * from central_attempts where attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if existing:
                if (
                    existing["lab_execution_id"] != execution_id
                    or existing["assignment_id"] != assignment_id
                ):
                    raise ValueError("central attempt identity changed on replay")
                return dict(existing), False
            latest = connection.execute(
                "select max(attempt) from central_attempts where lab_execution_id = ?",
                (execution_id,),
            ).fetchone()[0]
            attempt = int(latest or 0) + 1
            if attempt > max_attempts:
                raise ValueError("central execution exceeded its bounded attempt count")
            cursor = connection.execute(
                """
                insert into central_attempts(
                    attempt_id, lab_execution_id, assignment_id, attempt,
                    state, started_at
                ) values (?, ?, ?, ?, 'running', ?)
                on conflict(lab_execution_id, attempt) do nothing
                """,
                (attempt_id, execution_id, assignment_id, attempt, started_at),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                "select * from central_attempts where lab_execution_id = ? and attempt = ?",
                (execution_id, attempt),
            ).fetchone()
            connection.execute(
                """
                update central_executions
                set assignment_id = ?, updated_at = ?
                where lab_execution_id = ?
                """,
                (assignment_id, time.time(), execution_id),
            )
        return dict(row), created

    def acquire_central_resources(
        self, execution_id: str, assignment_id: str, resources: list[str]
    ) -> bool:
        if not resources:
            raise ValueError("central binding requires at least one resource")
        try:
            with self.transaction() as connection:
                for resource in sorted(set(resources)):
                    existing = connection.execute(
                        "select lab_execution_id from central_resource_leases where resource_id = ?",
                        (resource,),
                    ).fetchone()
                    if existing and existing["lab_execution_id"] == execution_id:
                        continue
                    connection.execute(
                        """
                        insert into central_resource_leases(
                            resource_id, lab_execution_id, assignment_id, acquired_at
                        ) values (?, ?, ?, ?)
                        """,
                        (resource, execution_id, assignment_id, time.time()),
                    )
            return True
        except sqlite3.IntegrityError:
            return False

    def release_central_resources(self, execution_id: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "delete from central_resource_leases where lab_execution_id = ?",
                (execution_id,),
            )

    def central_agent_status(self) -> dict[str, Any]:
        row = self._connection.execute(
            "select * from central_agent_control where singleton = 1"
        ).fetchone()
        value = dict(row)
        value["paused"] = bool(value["paused"])
        value["pending_executions"] = self._connection.execute(
            "select count(*) from central_executions where state in ('received', 'claimed')"
        ).fetchone()[0]
        value["pending_outbox"] = self._connection.execute(
            "select count(*) from central_outbox where state = 'pending'"
        ).fetchone()[0]
        value["active_leases"] = self._connection.execute(
            "select count(*) from central_resource_leases"
        ).fetchone()[0]
        return value

    def set_central_agent_paused(self, paused: bool) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                "update central_agent_control set paused = ?, updated_at = ? where singleton = 1",
                (int(paused), time.time()),
            )
        return self.central_agent_status()

    def record_central_agent_cycle(
        self, *, error: str | None, consecutive_failures: int, next_retry_at: float | None
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                update central_agent_control set consecutive_failures = ?,
                    last_error = ?, last_cycle_at = ?, next_retry_at = ?, updated_at = ?
                where singleton = 1
                """,
                (
                    consecutive_failures,
                    error[:2000] if error else None,
                    time.time(),
                    next_retry_at,
                    time.time(),
                ),
            )

    def finish_central_attempt(
        self,
        *,
        attempt_id: str,
        state: str,
        completed_at: str,
        pointer: Mapping[str, Any],
        cleanup_disposition: str,
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                update central_attempts
                set state = ?, completed_at = ?, pointer_json = ?, cleanup_disposition = ?
                where attempt_id = ? and state = 'running'
                """,
                (
                    state,
                    completed_at,
                    json.dumps(dict(pointer), sort_keys=True, separators=(",", ":")),
                    cleanup_disposition,
                    attempt_id,
                ),
            )

    def fail_running_central_attempt(self, execution_id: str, detail: str) -> None:
        completed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        with self.transaction() as connection:
            connection.execute(
                """
                update central_attempts
                set state = 'error', completed_at = ?, pointer_json = ?,
                    cleanup_disposition = 'error'
                where lab_execution_id = ? and completed_at is null
                """,
                (
                    completed_at,
                    json.dumps(
                        {"status": "error", "detail": detail[:2000]},
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                    execution_id,
                ),
            )

    def central_attempts(self, execution_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "select * from central_attempts where lab_execution_id = ? order by attempt",
            (execution_id,),
        ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            value = dict(row)
            if value.get("pointer_json"):
                value["pointer"] = json.loads(value.pop("pointer_json"))
            result.append(value)
        return result

    def enqueue_central_completion(
        self,
        *,
        execution_id: str,
        idempotency_key: str,
        body: Mapping[str, Any],
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                insert into central_outbox(
                    lab_execution_id, idempotency_key, body_json, state, updated_at
                ) values (?, ?, ?, 'pending', ?)
                on conflict(lab_execution_id) do nothing
                """,
                (
                    execution_id,
                    idempotency_key,
                    json.dumps(dict(body), sort_keys=True, separators=(",", ":")),
                    time.time(),
                ),
            )

    def central_outbox(self, execution_id: str) -> dict[str, Any] | None:
        row = self._connection.execute(
            "select * from central_outbox where lab_execution_id = ?",
            (execution_id,),
        ).fetchone()
        if row is None:
            return None
        value = dict(row)
        value["body"] = json.loads(value.pop("body_json"))
        return value

    def finish_central_outbox(
        self, execution_id: str, *, state: str, response_code: int
    ) -> None:
        with self.transaction() as connection:
            connection.execute(
                """
                update central_outbox
                set state = ?, response_code = ?, updated_at = ?
                where lab_execution_id = ?
                """,
                (state, response_code, time.time(), execution_id),
            )

    def create_event(
        self,
        *,
        event_key: str,
        repository_id: str,
        trigger_type: str,
        commit_sha: str,
        branch: str | None = None,
        pr_number: int | None = None,
        pr_url: str | None = None,
        contributor: str | None = None,
        changed_paths: list[str] | None = None,
        payload: Mapping[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        event_id = str(uuid.uuid4())
        now = time.time()
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                insert into events(
                    id, event_key, repository_id, trigger_type, commit_sha,
                    branch, pr_number, pr_url, contributor, changed_paths,
                    payload, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(event_key) do nothing
                """,
                (
                    event_id,
                    event_key,
                    repository_id,
                    trigger_type,
                    commit_sha.lower(),
                    branch,
                    pr_number,
                    pr_url,
                    contributor,
                    json.dumps(changed_paths or []),
                    json.dumps(dict(payload or {})),
                    now,
                ),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                "select * from events where event_key = ?", (event_key,)
            ).fetchone()
        return self._decode(row), created

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("database row not found")
        value = dict(row)
        for key in ("changed_paths", "payload"):
            if key in value and isinstance(value[key], str):
                value[key] = json.loads(value[key])
        return value

    def list_events(self, *, limit: int = 100, unplanned: bool = False) -> list[dict[str, Any]]:
        where = "where planned_at is null" if unplanned else ""
        rows = self._connection.execute(
            f"select * from events {where} order by created_at desc limit ?", (limit,)
        ).fetchall()
        return [self._decode(row) for row in rows]

    def mark_event_planned(self, event_id: str) -> None:
        with self.transaction() as connection:
            connection.execute(
                "update events set planned_at = ? where id = ?", (time.time(), event_id)
            )

    def create_gate_run(
        self,
        *,
        gate_id: str,
        event: Mapping[str, Any],
        definition_digest: str,
        required_policy: str,
        assignments: list[Mapping[str, str]],
        config_snapshot: Mapping[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        run_id = str(uuid.uuid4())
        now = time.time()
        with self.transaction() as connection:
            cursor = connection.execute(
                """
                insert into gate_runs(
                    id, gate_id, event_id, repository_id, commit_sha, branch,
                    pr_number, trigger_type, definition_digest, config_snapshot, status,
                    required_policy, created_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'queued', ?, ?)
                on conflict(gate_id, event_id, definition_digest) do nothing
                """,
                (
                    run_id,
                    gate_id,
                    event["id"],
                    event["repository_id"],
                    event["commit_sha"],
                    event.get("branch"),
                    event.get("pr_number"),
                    event["trigger_type"],
                    definition_digest,
                    json.dumps(dict(config_snapshot), sort_keys=True),
                    required_policy,
                    now,
                ),
            )
            created = cursor.rowcount == 1
            row = connection.execute(
                """select * from gate_runs
                   where gate_id = ? and event_id = ? and definition_digest = ?""",
                (gate_id, event["id"], definition_digest),
            ).fetchone()
            actual_run_id = row["id"]
            if created:
                for assignment in assignments:
                    connection.execute(
                        """
                        insert into assignments(
                            id, gate_run_id, setup_id, module_id, platform_key,
                            status, created_at
                        ) values (?, ?, ?, ?, ?, 'queued', ?)
                        """,
                        (
                            str(uuid.uuid4()),
                            actual_run_id,
                            assignment["setup_id"],
                            assignment["module_id"],
                            assignment["platform_key"],
                            now,
                        ),
                    )
        return dict(row), created

    def list_gate_runs(
        self, *, limit: int = 100, gate_id: str | None = None
    ) -> list[dict[str, Any]]:
        if gate_id:
            rows = self._connection.execute(
                "select * from gate_runs where gate_id = ? order by created_at desc limit ?",
                (gate_id, limit),
            ).fetchall()
        else:
            rows = self._connection.execute(
                "select * from gate_runs order by created_at desc limit ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item.pop("config_snapshot", None)
            result.append(item)
        return result

    def gate_run(self, run_id: str, *, include_config: bool = False) -> dict[str, Any]:
        row = self._connection.execute(
            """
            select gate_runs.*, events.contributor as requested_by,
                   events.payload as event_payload
            from gate_runs
            join events on events.id = gate_runs.event_id
            where gate_runs.id = ?
            """,
            (run_id,),
        ).fetchone()
        value = dict(row) if row else None
        if value is None:
            raise KeyError(run_id)
        snapshot = value.pop("config_snapshot", None)
        if include_config and isinstance(snapshot, str):
            value["config_snapshot"] = json.loads(snapshot)
        if isinstance(value.get("event_payload"), str):
            value["event_payload"] = json.loads(value["event_payload"])
        value["assignments"] = self.assignments(run_id)
        return value

    def assignments(self, run_id: str | None = None, *, status: str | None = None) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if run_id:
            clauses.append("gate_run_id = ?")
            parameters.append(run_id)
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"select * from assignments {where} order by created_at, setup_id, module_id",
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def assignment_attempts(self, assignment_id: str) -> list[dict[str, Any]]:
        rows = self._connection.execute(
            "select * from assignment_attempts where assignment_id = ? order by attempt",
            (assignment_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def next_assignment(self) -> dict[str, Any] | None:
        row = self._connection.execute(
            """
            select a.* from assignments a
            join gate_runs g on g.id = a.gate_run_id
            where a.status = 'queued' and g.status in ('queued', 'running')
            order by a.created_at limit 1
            """
        ).fetchone()
        return dict(row) if row else None

    def acquire(self, assignment_id: str, resources: list[str]) -> bool:
        now = time.time()
        try:
            with self.transaction() as connection:
                for resource in sorted(set(resources)):
                    connection.execute(
                        "insert into resource_leases(resource_id, assignment_id, acquired_at) values (?, ?, ?)",
                        (resource, assignment_id, now),
                    )
                connection.execute(
                    """update assignments set status = 'running', attempt = attempt + 1,
                       started_at = coalesce(started_at, ?) where id = ? and status = 'queued'""",
                    (now, assignment_id),
                )
                if connection.execute("select changes()").fetchone()[0] != 1:
                    raise sqlite3.IntegrityError("assignment is not queued")
                assignment = connection.execute(
                    "select attempt from assignments where id = ?", (assignment_id,)
                ).fetchone()
                connection.execute(
                    """
                    insert into assignment_attempts(
                        attempt_id, assignment_id, attempt, status, started_at
                    ) values (?, ?, ?, 'running', ?)
                    """,
                    (str(uuid.uuid4()), assignment_id, assignment["attempt"], now),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def finish_assignment(
        self,
        assignment_id: str,
        *,
        status: str,
        detail: str | None = None,
        result_pointer: str | None = None,
        qa_result_id: str | None = None,
        qa_result_url: str | None = None,
    ) -> None:
        with self.transaction() as connection:
            finished_at = time.time()
            connection.execute(
                """
                update assignments set status = ?, detail = ?, result_pointer = ?,
                    qa_result_id = ?, qa_result_url = ?, finished_at = ?
                where id = ?
                """,
                (
                    status,
                    detail,
                    result_pointer,
                    qa_result_id,
                    qa_result_url,
                    finished_at,
                    assignment_id,
                ),
            )
            attempt = connection.execute(
                "select attempt from assignments where id = ?", (assignment_id,)
            ).fetchone()
            if attempt and attempt["attempt"] > 0:
                connection.execute(
                    """
                    update assignment_attempts set status = ?, detail = ?,
                        result_pointer = ?, qa_result_id = ?, qa_result_url = ?,
                        finished_at = ?
                    where assignment_id = ? and attempt = ? and finished_at is null
                    """,
                    (
                        status,
                        detail,
                        result_pointer,
                        qa_result_id,
                        qa_result_url,
                        finished_at,
                        assignment_id,
                        attempt["attempt"],
                    ),
                )
            connection.execute(
                "delete from resource_leases where assignment_id = ?", (assignment_id,)
            )

    def record_assignment_artifacts(
        self, artifacts: list[Mapping[str, Any]]
    ) -> None:
        if not artifacts:
            return
        now = time.time()
        with self.transaction() as connection:
            for artifact in artifacts:
                connection.execute(
                    """
                    insert into assignment_artifacts(
                        id, assignment_id, attempt, relative_path, size_bytes,
                        sha256, media_type, storage_path, created_at
                    ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact["id"],
                        artifact["assignment_id"],
                        artifact["attempt"],
                        artifact["relative_path"],
                        artifact["size_bytes"],
                        artifact["sha256"],
                        artifact["media_type"],
                        artifact["storage_path"],
                        now,
                    ),
                )

    def assignment_artifacts(
        self, *, run_id: str | None = None, assignment_id: str | None = None
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        parameters: list[Any] = []
        if run_id:
            clauses.append("a.gate_run_id = ?")
            parameters.append(run_id)
        if assignment_id:
            clauses.append("aa.assignment_id = ?")
            parameters.append(assignment_id)
        where = f"where {' and '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"""
            select aa.*, a.gate_run_id, a.setup_id, a.module_id
            from assignment_artifacts aa
            join assignments a on a.id = aa.assignment_id
            {where}
            order by aa.created_at, aa.relative_path
            """,
            parameters,
        ).fetchall()
        return [dict(row) for row in rows]

    def assignment_artifact(self, run_id: str, artifact_id: str) -> dict[str, Any]:
        row = self._connection.execute(
            """
            select aa.*, a.gate_run_id, a.setup_id, a.module_id
            from assignment_artifacts aa
            join assignments a on a.id = aa.assignment_id
            where a.gate_run_id = ? and aa.id = ?
            """,
            (run_id, artifact_id),
        ).fetchone()
        if row is None:
            raise KeyError(artifact_id)
        return dict(row)

    def update_gate_run(
        self,
        run_id: str,
        *,
        status: str,
        summary: str | None = None,
        qa_result_id: str | None = None,
        qa_result_url: str | None = None,
    ) -> None:
        now = time.time()
        terminal = status in {"passed", "failed", "error", "skipped", "cancelled"}
        with self.transaction() as connection:
            connection.execute(
                """
                update gate_runs set status = ?, summary = coalesce(?, summary),
                    qa_result_id = coalesce(?, qa_result_id),
                    qa_result_url = coalesce(?, qa_result_url),
                    started_at = case when ? = 'running' then coalesce(started_at, ?) else started_at end,
                    finished_at = case when ? then ? else finished_at end
                where id = ?
                """,
                (
                    status,
                    summary,
                    qa_result_id,
                    qa_result_url,
                    status,
                    now,
                    terminal,
                    now,
                    run_id,
                ),
            )

    def recover_interrupted(self) -> int:
        """Fail closed after restart; devices need a fresh preflight before reuse."""
        with self.transaction() as connection:
            rows = connection.execute(
                "select id from assignments where status = 'running'"
            ).fetchall()
            for row in rows:
                connection.execute(
                    """
                    update assignment_attempts set status = 'error', detail = ?, finished_at = ?
                    where assignment_id = ? and finished_at is null
                    """,
                    ("orchestrator restarted while assignment was running", time.time(), row["id"]),
                )
                connection.execute(
                    "update assignments set status = 'error', detail = ?, finished_at = ? where id = ?",
                    ("orchestrator restarted while assignment was running", time.time(), row["id"]),
                )
            connection.execute("delete from resource_leases")
        return len(rows)

    def supersede_queued_pull_request(
        self, repository_id: str, pr_number: int, new_sha: str
    ) -> int:
        with self.transaction() as connection:
            rows = connection.execute(
                """
                select id from gate_runs
                where repository_id = ? and pr_number = ? and commit_sha != ?
                  and status = 'queued'
                """,
                (repository_id, pr_number, new_sha),
            ).fetchall()
            for row in rows:
                connection.execute(
                    "update assignments set status = 'superseded', finished_at = ? where gate_run_id = ? and status = 'queued'",
                    (time.time(), row["id"]),
                )
                connection.execute(
                    "update gate_runs set status = 'superseded', finished_at = ? where id = ?",
                    (time.time(), row["id"]),
                )
        return len(rows)

    def cancel_gate_run(self, run_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            running = connection.execute(
                "select count(*) from assignments where gate_run_id = ? and status = 'running'",
                (run_id,),
            ).fetchone()[0]
            connection.execute(
                "update assignments set status = 'cancelled', finished_at = ? where gate_run_id = ? and status = 'queued'",
                (time.time(), run_id),
            )
            if not running:
                connection.execute(
                    "update gate_runs set status = 'cancelled', finished_at = ? where id = ?",
                    (time.time(), run_id),
                )
        return self.gate_run(run_id)

    def retry_gate_run(self, run_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            connection.execute(
                """
                update assignments set status = 'queued', detail = null,
                    result_pointer = null, qa_result_id = null, qa_result_url = null,
                    started_at = null, finished_at = null
                where gate_run_id = ? and status in ('failed', 'error', 'cancelled', 'superseded')
                """,
                (run_id,),
            )
            changed = connection.execute("select changes()").fetchone()[0]
            if changed:
                connection.execute(
                    "update gate_runs set status = 'queued', summary = null, started_at = null, finished_at = null where id = ?",
                    (run_id,),
                )
        return self.gate_run(run_id)

    def apply_remote_rerun(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = str(request["id"])
        run_id = str(request["external_run_id"])
        with self.transaction() as connection:
            existing = connection.execute(
                "select * from remote_rerun_requests where request_id = ?",
                (request_id,),
            ).fetchone()
            if existing:
                if (
                    existing["public_gate_run_id"] != request.get("gate_run_id")
                    or existing["local_gate_run_id"] != run_id
                    or existing["mode"] != request.get("mode")
                ):
                    raise ValueError("public rerun request identity changed after application")
                if request.get("mode") == "assignments" and json.loads(
                    existing["assignment_ids"]
                ) != list(dict.fromkeys(request.get("assignment_ids") or [])):
                    raise ValueError("public rerun request assignments changed after application")
                run_id = existing["local_gate_run_id"]
                applied = False
            else:
                row = connection.execute(
                    "select * from gate_runs where id = ?", (run_id,)
                ).fetchone()
                if row is None:
                    raise ValueError("public rerun references an unknown local run")
                run = dict(row)
                if run.get("qa_result_id") != request.get("gate_run_id"):
                    raise ValueError("public rerun parent identity does not match local state")
                if run["gate_id"] != request.get("gate_key"):
                    raise ValueError("public rerun gate does not match local state")
                if run["commit_sha"] != request.get("commit_sha"):
                    raise ValueError("public rerun commit does not match local state")
                snapshot = json.loads(run["config_snapshot"])
                repository = snapshot.get("repositories", {}).get(run["repository_id"], {})
                if repository.get("repository") != request.get("repository"):
                    raise ValueError("public rerun repository does not match local state")
                if run["status"] not in {"passed", "failed", "error", "cancelled"}:
                    raise ValueError("public rerun local run is active or not eligible")

                assignment_rows = connection.execute(
                    "select id, status from assignments where gate_run_id = ? order by created_at",
                    (run_id,),
                ).fetchall()
                assignments = {item["id"]: item["status"] for item in assignment_rows}
                if request.get("mode") == "all":
                    target_ids = list(assignments)
                elif request.get("mode") == "assignments":
                    target_ids = list(dict.fromkeys(request.get("assignment_ids") or []))
                    if not target_ids or any(item not in assignments for item in target_ids):
                        raise ValueError("public rerun assignment does not match local state")
                else:
                    raise ValueError("public rerun mode is invalid")
                if not target_ids:
                    raise ValueError("public rerun has no local assignments")
                if any(assignments[item] in {"queued", "running"} for item in target_ids):
                    raise ValueError("public rerun cannot interrupt active assignments")

                assignment_update = """
                    update assignments set status = 'queued', detail = null,
                        result_pointer = null, qa_result_id = null, qa_result_url = null,
                        started_at = null, finished_at = null
                    where gate_run_id = ?
                """
                parameters: tuple[Any, ...] = (run_id,)
                if request.get("mode") == "assignments":
                    placeholders = ",".join("?" for _ in target_ids)
                    assignment_update += f" and id in ({placeholders})"
                    parameters = (run_id, *target_ids)
                connection.execute(assignment_update, parameters)
                if connection.execute("select changes()").fetchone()[0] != len(target_ids):
                    raise ValueError("public rerun assignments changed during validation")
                connection.execute(
                    """
                    update gate_runs set status = 'queued', summary = null,
                        started_at = null, finished_at = null where id = ?
                    """,
                    (run_id,),
                )
                connection.execute(
                    """
                    insert into remote_rerun_requests(
                        request_id, public_gate_run_id, local_gate_run_id, mode,
                        assignment_ids, applied_at
                    ) values (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request_id,
                        request["gate_run_id"],
                        run_id,
                        request["mode"],
                        json.dumps(target_ids),
                        time.time(),
                    ),
                )
                applied = True
        return {"applied": applied, "run": self.gate_run(run_id)}
