from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, urlopen

from .config import ConfigStore
from .database import OrchestratorDatabase
from .errors import ConfigError


MAX_BODY_BYTES = 256 * 1024
MAX_RUNNER_OUTPUT_BYTES = 1024 * 1024
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_OFFER_KEYS = frozenset(
    {
        "central_gate_run_id",
        "lab_execution_id",
        "lab_id",
        "public_lab_label",
        "platform_class",
        "device_model",
        "definition_digest",
        "definition",
        "source",
        "offered_at",
        "deadline_at",
        "claim_ttl_seconds",
        "max_claim_generations",
    }
)
_CANARIES = (
    "device-canary-east",
    "device-canary-west",
    "pool-canary-worker",
    "/private/canary/path",
    "192.0.2.44",
)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _canonical(value: Any) -> str:
    if isinstance(value, float) or isinstance(value, bool):
        if isinstance(value, float):
            raise ValueError("portable definitions cannot contain floats")
    if isinstance(value, list):
        return "[" + ",".join(_canonical(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join(
            json.dumps(str(key), ensure_ascii=False) + ":" + _canonical(value[key])
            for key in sorted(value)
        ) + "}"
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


class CoordinationHttpError(RuntimeError):
    def __init__(self, status: int, body: Mapping[str, Any]) -> None:
        self.status = status
        self.body = dict(body)
        code = self.body.get("error", {}).get("code", "http_error")
        super().__init__(f"coordination request returned HTTP {status} ({code})")


class CoordinationClient:
    def __init__(self, base_url: str, token: str, timeout: float) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        *,
        query: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            url = f"{url}?{urlencode(query)}"
        encoded = None
        headers = {"Accept": "application/json", "Authorization": f"Bearer {self.token}"}
        if body is not None:
            encoded = json.dumps(body, separators=(",", ":")).encode()
            if len(encoded) > MAX_BODY_BYTES:
                raise ConfigError("coordination request exceeds 256 KiB")
            headers["Content-Type"] = "application/json"
        request = Request(url, data=encoded, headers=headers, method=method)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_BODY_BYTES + 1)
                status = response.status
        except HTTPError as exc:
            raw = exc.read(MAX_BODY_BYTES + 1)
            status = exc.code
        except (URLError, OSError, TimeoutError) as exc:
            raise ConfigError(f"bounded coordination request failed: {type(exc).__name__}") from exc
        if len(raw) > MAX_BODY_BYTES:
            raise ConfigError("coordination response exceeds 256 KiB")
        try:
            value = json.loads(raw or b"{}")
        except json.JSONDecodeError as exc:
            raise ConfigError("coordination response is not JSON") from exc
        if not isinstance(value, dict):
            raise ConfigError("coordination response is not an object")
        if not 200 <= status < 300:
            raise CoordinationHttpError(status, value)
        return value


def _strict_object(value: Any, keys: frozenset[str], context: str) -> dict[str, Any]:
    if not isinstance(value, dict) or frozenset(value) != keys:
        raise ValueError(f"{context} has invalid fields")
    return value


def _opaque(value: Any, context: str) -> str:
    if not isinstance(value, str) or not _OPAQUE.fullmatch(value):
        raise ValueError(f"{context} is not an opaque identifier")
    return value


def _timestamp(value: Any, context: str) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"{context} is not a bounded timestamp")
    datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


def validate_offer(value: Any, expected_lab: str) -> dict[str, Any]:
    offer = _strict_object(value, _OFFER_KEYS, "offer")
    for key in ("central_gate_run_id", "lab_execution_id", "lab_id"):
        _opaque(offer[key], f"offer.{key}")
    if offer["lab_id"] != expected_lab:
        raise ValueError("offer.lab_id does not match configured lab")
    for key in ("public_lab_label", "platform_class", "device_model"):
        if not isinstance(offer[key], str) or not 1 <= len(offer[key]) <= 80:
            raise ValueError(f"offer.{key} is invalid")
    digest = offer["definition_digest"]
    if not isinstance(digest, str) or not _DIGEST.fullmatch(digest):
        raise ValueError("offer.definition_digest is invalid")
    definition = _strict_object(
        offer["definition"], frozenset({"project", "gate", "suite", "trigger"}), "definition"
    )
    project = _strict_object(definition["project"], frozenset({"id", "repository"}), "project")
    gate = _strict_object(definition["gate"], frozenset({"id", "revision_id"}), "gate")
    suite = _strict_object(
        definition["suite"], frozenset({"id", "revision_id", "requirements"}), "suite"
    )
    trigger = _strict_object(
        definition["trigger"], frozenset({"id", "revision_id", "type"}), "trigger"
    )
    for item, fields in ((project, ("id",)), (gate, ("id", "revision_id")), (suite, ("id", "revision_id")), (trigger, ("id", "revision_id"))):
        for field in fields:
            _opaque(item[field], field)
    if not _REPOSITORY.fullmatch(str(project["repository"])) or trigger["type"] != "manual":
        raise ValueError("portable project or trigger is invalid")
    requirements = suite["requirements"]
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 32:
        raise ValueError("suite.requirements is invalid")
    requirement_keys = frozenset(
        {"requirement_id", "platform_class", "device_model", "capabilities", "test_pattern"}
    )
    for requirement in requirements:
        parsed = _strict_object(requirement, requirement_keys, "requirement")
        _opaque(parsed["requirement_id"], "requirement.requirement_id")
        if not isinstance(parsed["capabilities"], list) or not parsed["capabilities"]:
            raise ValueError("requirement.capabilities is invalid")
        for capability in parsed["capabilities"]:
            _opaque(capability, "requirement.capability")
        pattern = parsed["test_pattern"]
        if not isinstance(pattern, str) or ".." in pattern or len(pattern) > 200:
            raise ValueError("requirement.test_pattern is unsafe")
    source = _strict_object(
        offer["source"], frozenset({"repository", "commit_sha", "ref_name", "pr_number"}), "source"
    )
    if not _REPOSITORY.fullmatch(str(source["repository"])) or not _SHA.fullmatch(str(source["commit_sha"])):
        raise ValueError("source provenance is invalid")
    if not isinstance(source["ref_name"], str) or len(source["ref_name"]) > 255:
        raise ValueError("source.ref_name is invalid")
    if source["pr_number"] is not None and (
        isinstance(source["pr_number"], bool)
        or not isinstance(source["pr_number"], int)
        or source["pr_number"] <= 0
    ):
        raise ValueError("source.pr_number is invalid")
    _timestamp(offer["offered_at"], "offer.offered_at")
    deadline = _timestamp(offer["deadline_at"], "offer.deadline_at")
    if datetime.fromisoformat(deadline.replace("Z", "+00:00")) <= datetime.now(UTC):
        raise ValueError("offer deadline has passed")
    if not isinstance(offer["claim_ttl_seconds"], int) or not 30 <= offer["claim_ttl_seconds"] <= 900:
        raise ValueError("offer.claim_ttl_seconds is invalid")
    if not isinstance(offer["max_claim_generations"], int) or not 1 <= offer["max_claim_generations"] <= 5:
        raise ValueError("offer.max_claim_generations is invalid")
    if canonical_digest(definition) != digest:
        raise ValueError("definition digest mismatch")
    return offer


@dataclass(frozen=True, slots=True)
class CentralSettings:
    base_url: str
    lab_id: str
    token: str
    timeout: float
    subscriptions: tuple[str, ...]
    state_dir: Path
    bindings: Mapping[str, Mapping[str, Any]]

    @classmethod
    def from_store(cls, store: ConfigStore) -> "CentralSettings":
        document = store.snapshot.document
        coordination = document["coordination"]
        if coordination["mode"] != "central":
            raise ConfigError("central-once requires coordination.mode: central")
        central = coordination["central"]
        token_env = str(central.get("token_env", "MINING_QA_LAB_AGENT_TOKEN"))
        token = os.environ.get(token_env, "").strip()
        if not token:
            raise ConfigError(f"central Lab token environment is not set: {token_env}")
        state_dir = Path(document["controller"]["state_dir"])
        if not state_dir.is_absolute():
            state_dir = (store.source.parent / state_dir).resolve()
        return cls(
            base_url=str(central["base_url"]),
            lab_id=str(central["lab_id"]),
            token=token,
            timeout=float(central["request_timeout_seconds"]),
            subscriptions=tuple(central["subscriptions"]["gates"]),
            state_dir=state_dir,
            bindings=document["bindings"]["suite_requirements"],
        )


class CentralAgent:
    def __init__(self, settings: CentralSettings, database: OrchestratorDatabase) -> None:
        self.settings = settings
        self.database = database
        self.client = CoordinationClient(settings.base_url, settings.token, settings.timeout)

    def announce(self) -> None:
        nonce = uuid.uuid4().hex
        self.client.request(
            "POST",
            f"/api/v2/labs/{quote(self.settings.lab_id)}/heartbeat",
            {
                "contract_version": 2,
                "idempotency_key": f"heartbeat-{nonce}",
                "agent_version": "mining-qa-lab/0.1.0",
                "sent_at": _now(),
                "available_slots": 1,
                "capabilities": [
                    {
                        "platform_class": "gamma-600",
                        "device_model": "Gamma 602",
                        "features": ["api", "pool-config", "stratum-v1"],
                        "aggregate_state": "available",
                        "evidence_at": _now(),
                    }
                ],
                "health_code": "ok",
            },
        )
        self.client.request(
            "PUT",
            f"/api/v2/labs/{quote(self.settings.lab_id)}/subscriptions",
            {
                "contract_version": 2,
                "idempotency_key": "subscriptions-v1",
                "revision": 1,
                "gate_ids": list(self.settings.subscriptions),
            },
        )

    def pull(self, *, replay_from_zero: bool = False) -> list[dict[str, Any]]:
        cursor_row = self.database.cursor(f"central:{self.settings.lab_id}")
        after = "0" if replay_from_zero else str(cursor_row["value"] if cursor_row else "0")
        page = self.client.request(
            "GET",
            f"/api/v2/labs/{quote(self.settings.lab_id)}/work",
            query={"after": after, "limit": "32"},
        )
        if page.get("contract_version") != 2 or not isinstance(page.get("offers"), list):
            raise ConfigError("work page does not implement coordination contract v2")
        cursor = str(page.get("cursor", ""))
        if len(cursor) > 256 or not cursor.isdigit():
            raise ConfigError("work page cursor is invalid")
        raw_offers: list[dict[str, Any]] = []
        for item in page["offers"]:
            if not isinstance(item, dict) or len(json.dumps(item).encode()) > 64 * 1024:
                raise ConfigError("work page contains an invalid or oversized offer")
            raw_offers.append(item)
        self.database.persist_central_page(
            lab_id=self.settings.lab_id,
            cursor=cursor,
            offers=raw_offers,
        )
        return raw_offers

    def _decline(self, offer: Mapping[str, Any], reason: str) -> None:
        execution_id = _opaque(offer.get("lab_execution_id"), "offer.lab_execution_id")
        observed = str(offer.get("definition_digest", ""))
        if not _DIGEST.fullmatch(observed):
            observed = "0" * 64
            reason = "invalid_offer"
        self.client.request(
            "POST",
            f"/api/v2/executions/{quote(execution_id)}/decline",
            {
                "contract_version": 2,
                "idempotency_key": f"decline-{_stable_id('id', execution_id)}",
                "lab_id": self.settings.lab_id,
                "observed_definition_digest": observed,
                "claim": None,
                "reason_code": reason,
            },
        )
        self.database.update_central_execution(execution_id, state="declined")

    def _binding(self, offer: Mapping[str, Any]) -> Mapping[str, Any] | None:
        requirements = offer["definition"]["suite"]["requirements"]
        matches = [self.settings.bindings[item["requirement_id"]] for item in requirements if item["requirement_id"] in self.settings.bindings]
        return matches[0] if len(matches) == 1 and len(requirements) == 1 else None

    def _claim(self, execution: Mapping[str, Any], *, next_generation: bool = False) -> dict[str, Any]:
        generation = int(execution.get("claim_generation") or 0)
        desired = generation + 1 if next_generation or not generation else generation
        response = self.client.request(
            "POST",
            f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/claim",
            {
                "contract_version": 2,
                "idempotency_key": f"claim-{_stable_id('id', str(execution['lab_execution_id']))}-{desired}",
                "lab_id": self.settings.lab_id,
                "definition_digest": execution["definition_digest"],
            },
        )
        if os.environ.get("MINING_QA_INTEGRATION_REPLAY") == "1":
            replay = self.client.request(
                "POST",
                f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/claim",
                {
                    "contract_version": 2,
                    "idempotency_key": f"claim-{_stable_id('id', str(execution['lab_execution_id']))}-{desired}",
                    "lab_id": self.settings.lab_id,
                    "definition_digest": execution["definition_digest"],
                },
            )
            if replay != response:
                raise ConfigError("claim replay did not return the original response")
        self.database.update_central_execution(
            str(execution["lab_execution_id"]),
            state="claimed",
            claim_id=str(response["claim_id"]),
            claim_generation=int(response["claim_generation"]),
            claim_token=str(response["claim_token"]),
            claim_expires_at=str(response["lease_expires_at"]),
        )
        return response

    def _renew(self, execution: Mapping[str, Any]) -> None:
        response = self.client.request(
            "POST",
            f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/renew",
            {
                "contract_version": 2,
                "idempotency_key": f"renew-{_stable_id('id', str(execution['lab_execution_id']))}-{execution['claim_generation']}",
                "claim_id": execution["claim_id"],
                "claim_generation": execution["claim_generation"],
                "claim_token": execution["claim_token"],
            },
        )
        self.database.update_central_execution(
            str(execution["lab_execution_id"]), claim_expires_at=str(response["lease_expires_at"])
        )

    def _testcode_identity(self, root: Path) -> tuple[str, str]:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()
        ref = subprocess.run(
            ["git", "branch", "--show-current"], cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip() or "detached"
        if not _SHA.fullmatch(sha):
            raise ConfigError("testcode checkout did not resolve to an exact commit")
        return sha, ref

    def _run_testcode(
        self,
        execution: Mapping[str, Any],
        binding: Mapping[str, Any],
        behavior: str,
    ) -> tuple[dict[str, Any], str, str, str]:
        offer = execution["offer"]
        execution_id = str(execution["lab_execution_id"])
        assignment_id = _stable_id("assignment", execution_id)
        attempt_id = _stable_id("attempt", f"{execution_id}:1")
        local_run_id = _stable_id("local", execution_id)
        started_at = _now()
        attempt, created = self.database.start_central_attempt(
            execution_id=execution_id,
            assignment_id=assignment_id,
            attempt_id=attempt_id,
            started_at=started_at,
        )
        if not created:
            raise ConfigError(f"central execution {execution_id} already has a runner attempt")
        root = Path(str(binding["testcode_root"])).resolve()
        profile = Path(str(binding["profile"])).resolve()
        sha, ref = self._testcode_identity(root)
        source = offer["source"]
        definition = offer["definition"]
        metadata = {
            "contract_version": 2,
            "project_id": definition["project"]["id"],
            "gate_id": definition["gate"]["id"],
            "gate_revision_id": definition["gate"]["revision_id"],
            "suite_id": definition["suite"]["id"],
            "suite_revision_id": definition["suite"]["revision_id"],
            "trigger_id": definition["trigger"]["id"],
            "trigger_revision_id": definition["trigger"]["revision_id"],
            "trigger_type": definition["trigger"]["type"],
            "definition_digest": execution["definition_digest"],
            "central_gate_run_id": execution["central_gate_run_id"],
            "lab_id": self.settings.lab_id,
            "public_lab_label": offer["public_lab_label"],
            "platform_class": offer["platform_class"],
            "device_model": offer["device_model"],
            "lab_execution_id": execution_id,
            "local_gate_run_id": local_run_id,
            "assignment_id": assignment_id,
            "attempt_id": attempt_id,
            "attempt": 1,
            "source": source,
            "testcode": {
                "repository": "johnny9/mining-qa-testcode",
                "ref": ref,
                "commit_sha": sha,
            },
        }
        work = self.settings.state_dir / "central-artifacts" / execution_id
        work.mkdir(parents=True, exist_ok=True)
        pointer_path = work / "result-pointer.json"
        artifacts_path = work / "runner"
        mock_env = str(binding.get("mock_base_url_env", "MINING_QA_MOCK_URL"))
        mock_url = os.environ.get(mock_env, "").strip()
        if urlsplit(mock_url).hostname not in {"127.0.0.1", "::1", "localhost"}:
            raise ConfigError("central integration binding requires a loopback mock device")
        mock_scenario = {
            "pass": "pass",
            "test-failure": "test-failure",
            "cleanup-restore-rejected": "cleanup-restore-rejected",
        }.get(behavior)
        if mock_scenario is None:
            raise ConfigError(f"unsupported integration behavior: {behavior}")
        CoordinationClient(mock_url, "", self.settings.timeout).request(
            "POST",
            "/__mock/v1/reset",
            {
                "contract_version": 1,
                "scenario": mock_scenario,
                "baseline": "gamma-running",
                "privacy_canaries": list(_CANARIES),
            },
        )
        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONPATH": str(root / "src"),
                "MINING_QA_MOCK_URL": mock_url,
                "MINING_QA_TEST_ARTIFACTS": str(artifacts_path),
                "MINING_QA_URL": self.settings.base_url,
                "MINER_TEST_ORCHESTRATION_METADATA": json.dumps(metadata, separators=(",", ":")),
                "MINER_TEST_EXTERNAL_RUN_ID": assignment_id,
                "MINER_TEST_RESULT_POINTER": str(pointer_path),
                "GITHUB_REPOSITORY": str(source["repository"]),
                "GITHUB_SHA": str(source["commit_sha"]),
                "GITHUB_REF_NAME": str(source["ref_name"]),
                "MINING_QA_INTEGRATION_DEVELOPMENT": "1",
                "MINER_TEST_PRIVACY_CANARIES": json.dumps(_CANARIES),
            }
        )
        if source["pr_number"] is None:
            environment.pop("MINER_TEST_PR_NUMBER", None)
        else:
            environment["MINER_TEST_PR_NUMBER"] = str(source["pr_number"])
        result = subprocess.run(
            [sys.executable, "-m", "miner_testcode", "--config", str(profile)],
            cwd=root,
            env=environment,
            capture_output=True,
            timeout=60,
        )
        if len(result.stdout) + len(result.stderr) > MAX_RUNNER_OUTPUT_BYTES:
            raise ConfigError("runner output exceeded 1 MiB")
        process_log = (result.stdout + b"\n" + result.stderr).decode(
            "utf-8", errors="replace"
        )
        for canary in _CANARIES:
            process_log = process_log.replace(canary, "<redacted-canary>")
        (work / "runner-process.log").write_text(process_log, encoding="utf-8")
        (work / "runner-process.log").chmod(0o600)
        try:
            raw_pointer = pointer_path.read_bytes()
        except FileNotFoundError as exc:
            raise ConfigError(f"runner exited {result.returncode} without a result pointer") from exc
        if len(raw_pointer) > 64 * 1024:
            raise ConfigError("runner result pointer exceeds 64 KiB")
        pointer = json.loads(raw_pointer)
        expected_correlation = {
            "central_gate_run_id": execution["central_gate_run_id"],
            "lab_id": self.settings.lab_id,
            "lab_execution_id": execution_id,
            "local_gate_run_id": local_run_id,
            "assignment_id": assignment_id,
            "attempt_id": attempt_id,
            "definition_digest": execution["definition_digest"],
        }
        if pointer.get("contract_version") != 2 or pointer.get("correlation") != expected_correlation:
            raise ConfigError("runner pointer does not match immutable orchestration v2 input")
        status = pointer.get("status")
        if status not in {"passed", "failed", "error", "skipped"}:
            raise ConfigError("runner pointer has an invalid terminal status")
        publisher = next(
            (
                item
                for item in pointer.get("publishers", [])
                if item.get("name") == "mining_qa_status" and item.get("success") is True
            ),
            None,
        )
        if not publisher or not _OPAQUE.fullmatch(str(publisher.get("result_id", ""))):
            raise ConfigError("runner pointer lacks a published Status child result")
        completed_at = _now()
        cleanup = "error" if behavior == "cleanup-restore-rejected" else "restored"
        self.database.finish_central_attempt(
            attempt_id=attempt_id,
            state=str(status),
            completed_at=completed_at,
            pointer=pointer,
            cleanup_disposition=cleanup,
        )
        return pointer, started_at, completed_at, sha

    def _completion(
        self,
        execution: Mapping[str, Any],
        pointer: Mapping[str, Any],
        started_at: str,
        completed_at: str,
        testcode_sha: str,
    ) -> dict[str, Any]:
        offer = execution["offer"]
        definition = offer["definition"]
        attempt = self.database.central_attempts(str(execution["lab_execution_id"]))[0]
        publisher = next(item for item in pointer["publishers"] if item["name"] == "mining_qa_status")
        return {
            "contract_version": 2,
            "idempotency_key": f"complete-{_stable_id('id', str(execution['lab_execution_id']))}",
            "claim": {
                "claim_id": execution["claim_id"],
                "claim_generation": execution["claim_generation"],
                "claim_token": execution["claim_token"],
            },
            "private_correlation": {
                "central_gate_run_id": execution["central_gate_run_id"],
                "lab_execution_id": execution["lab_execution_id"],
                "lab_id": self.settings.lab_id,
                "local_gate_run_id": pointer["correlation"]["local_gate_run_id"],
                "definition_digest": execution["definition_digest"],
            },
            "published_completion": {
                "central_gate_run_id": execution["central_gate_run_id"],
                "lab_execution_id": execution["lab_execution_id"],
                "lab_id": self.settings.lab_id,
                "public_lab_label": offer["public_lab_label"],
                "platform_class": offer["platform_class"],
                "device_model": offer["device_model"],
                "project_id": definition["project"]["id"],
                "gate_id": definition["gate"]["id"],
                "gate_revision_id": definition["gate"]["revision_id"],
                "suite_id": definition["suite"]["id"],
                "suite_revision_id": definition["suite"]["revision_id"],
                "trigger_id": definition["trigger"]["id"],
                "trigger_revision_id": definition["trigger"]["revision_id"],
                "definition_digest": execution["definition_digest"],
                "outcome": pointer["status"],
                "started_at": started_at,
                "completed_at": completed_at,
                "source": offer["source"],
                "testcode": {
                    "repository": "johnny9/mining-qa-testcode",
                    "ref": self._testcode_identity(Path(str(self._binding(offer)["testcode_root"])))[1],
                    "commit_sha": testcode_sha,
                },
                "children": [
                    {
                        "assignment_id": attempt["assignment_id"],
                        "attempt_id": attempt["attempt_id"],
                        "runner_run_id": pointer["run_id"],
                        "status": pointer["status"],
                        "result_id": publisher["result_id"],
                        "result_url": publisher["url"],
                    }
                ],
                "reason_code": None,
            },
        }

    def _flush(self, execution: Mapping[str, Any]) -> str:
        outbox = self.database.central_outbox(str(execution["lab_execution_id"]))
        if not outbox:
            raise ConfigError("central completion outbox is missing")
        try:
            response = self.client.request(
                "POST",
                f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/complete",
                outbox["body"],
            )
        except CoordinationHttpError as exc:
            if exc.status == 409 and exc.body.get("error", {}).get("code") == "claim_expired":
                self.database.finish_central_outbox(
                    str(execution["lab_execution_id"]), state="conflict", response_code=409
                )
                self.database.update_central_execution(str(execution["lab_execution_id"]), state="conflict")
                return "conflict"
            raise
        if os.environ.get("MINING_QA_INTEGRATION_REPLAY") == "1":
            replay = self.client.request(
                "POST",
                f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/complete",
                outbox["body"],
            )
            if replay != response:
                raise ConfigError("completion replay did not return the original response")
        self.database.finish_central_outbox(
            str(execution["lab_execution_id"]), state="delivered", response_code=200
        )
        self.database.update_central_execution(
            str(execution["lab_execution_id"]), state="completed", claim_token=None
        )
        return "completed"

    def process(self, *, phase: str, behavior: str, replay_from_zero: bool = False) -> list[str]:
        self.announce()
        self.pull(replay_from_zero=replay_from_zero)
        results: list[str] = []
        for saved in self.database.pending_central_executions(self.settings.lab_id):
            offer = saved["offer"]
            try:
                validated = validate_offer(offer, self.settings.lab_id)
            except (TypeError, ValueError):
                self._decline(offer, "definition_mismatch" if set(offer) == set(_OFFER_KEYS) else "invalid_offer")
                results.append("declined")
                continue
            binding = self._binding(validated)
            if behavior == "decline-no-safe-binding" or binding is None:
                self._decline(validated, "no_safe_binding")
                results.append("declined")
                continue
            execution = self.database.central_execution(str(saved["lab_execution_id"]))
            if execution is None:
                raise ConfigError("persisted central execution disappeared")
            attempts = self.database.central_attempts(str(execution["lab_execution_id"]))
            if attempts and attempts[0]["state"] != "running":
                results.append(self._flush(execution))
                continue
            if phase == "reclaim":
                self._claim(execution, next_generation=True)
            elif execution["state"] != "claimed":
                self._claim(execution)
            execution = self.database.central_execution(str(execution["lab_execution_id"]))
            if execution is None:
                raise ConfigError("claimed central execution disappeared")
            if phase == "claim-only":
                results.append("claimed")
                continue
            self._renew(execution)
            execution = self.database.central_execution(str(execution["lab_execution_id"]))
            if execution is None:
                raise ConfigError("renewed central execution disappeared")
            pointer, started_at, completed_at, sha = self._run_testcode(execution, binding, behavior)
            completion = self._completion(execution, pointer, started_at, completed_at, sha)
            self.database.enqueue_central_completion(
                execution_id=str(execution["lab_execution_id"]),
                idempotency_key=str(completion["idempotency_key"]),
                body=completion,
            )
            results.append(self._flush(execution))
        return results


def run_central_once(
    store: ConfigStore,
    database: OrchestratorDatabase,
    *,
    phase: str = "run",
    replay_from_zero: bool = False,
) -> list[str]:
    if phase not in {"run", "claim-only", "reclaim"}:
        raise ConfigError("central integration phase must be run, claim-only, or reclaim")
    settings = CentralSettings.from_store(store)
    behavior = os.environ.get("MINING_QA_INTEGRATION_BEHAVIOR", "pass")
    if urlsplit(settings.base_url).hostname not in {"127.0.0.1", "::1", "localhost"} and (
        phase != "run" or behavior != "pass" or replay_from_zero
    ):
        raise ConfigError("integration-only central controls require a loopback Status service")
    return CentralAgent(settings, database).process(
        phase=phase,
        behavior=behavior,
        replay_from_zero=replay_from_zero,
    )
