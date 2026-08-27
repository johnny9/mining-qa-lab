from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
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
AGENT_VERSION = "mining-qa-lab/0.1.0"
_DEFAULT_RUNNER_ENVIRONMENT = frozenset(
    {
        "PATH",
        "LANG",
        "LC_ALL",
        "TZ",
        "TMPDIR",
        "MINING_QA_TOKEN",
        "MINER_TEST_POOL_USER",
        "MINER_TEST_POOL_PASSWORD",
        "MINER_TEST_FAKE_STRATUM_PASSWORD",
        "MINER_CURRENT_POOL_PASSWORD",
    }
)
_CONTRACT_ENVIRONMENT = frozenset(
    {
        "MINER_TEST_ORCHESTRATION_METADATA",
        "MINER_TEST_EXTERNAL_RUN_ID",
        "MINER_TEST_RESULT_POINTER",
        "GITHUB_REPOSITORY",
        "GITHUB_SHA",
        "GITHUB_REF_NAME",
        "MINER_TEST_PR_NUMBER",
        "MINER_TEST_MODULE_OPTIONS",
    }
)
_OPAQUE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_AGENT_TOKEN = re.compile(r"^mqa_[A-Za-z0-9_-]{16,120}$")
_PRIVATE_OPTION_PART = re.compile(
    r"address|command|credential|device|endpoint|environment|host|password|path|pool|secret|serial|token|url|user|worker",
    re.IGNORECASE,
)
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


def _strict_object_with_optional(
    value: Any,
    required: frozenset[str],
    optional: frozenset[str],
    context: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} has invalid fields")
    actual = frozenset(value)
    if not required.issubset(actual) or not actual.issubset(required | optional):
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
    suite = _strict_object_with_optional(
        definition["suite"],
        frozenset({"id", "revision_id", "requirements"}),
        frozenset({"testcode_catalog"}),
        "suite",
    )
    trigger = _strict_object(
        definition["trigger"], frozenset({"id", "revision_id", "type"}), "trigger"
    )
    for item, fields in ((project, ("id",)), (gate, ("id", "revision_id")), (suite, ("id", "revision_id")), (trigger, ("id", "revision_id"))):
        for field in fields:
            _opaque(item[field], field)
    if (
        not _REPOSITORY.fullmatch(str(project["repository"]))
        or trigger["type"] not in {"manual", "push", "pull_request"}
    ):
        raise ValueError("portable project or trigger is invalid")
    if "testcode_catalog" in suite:
        catalog_source = _strict_object(
            suite["testcode_catalog"],
            frozenset({"repository", "ref", "commit_sha"}),
            "suite.testcode_catalog",
        )
        if (
            not _REPOSITORY.fullmatch(str(catalog_source.get("repository", "")))
            or not isinstance(catalog_source.get("ref"), str)
            or not 1 <= len(catalog_source["ref"]) <= 255
            or not _SHA.fullmatch(str(catalog_source.get("commit_sha", "")))
        ):
            raise ValueError("suite.testcode_catalog is invalid")
    requirements = suite["requirements"]
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 32:
        raise ValueError("suite.requirements is invalid")
    requirement_keys = frozenset(
        {
            "requirement_id",
            "platform_class",
            "device_model",
            "capabilities",
            "test_pattern",
        }
    )
    for requirement in requirements:
        parsed = _strict_object_with_optional(
            requirement,
            requirement_keys,
            frozenset({"module_id", "options"}),
            "requirement",
        )
        _opaque(parsed["requirement_id"], "requirement.requirement_id")
        if "module_id" in parsed:
            _opaque(parsed["module_id"], "requirement.module_id")
        if not isinstance(parsed["capabilities"], list) or not parsed["capabilities"]:
            raise ValueError("requirement.capabilities is invalid")
        for capability in parsed["capabilities"]:
            _opaque(capability, "requirement.capability")
        pattern = parsed["test_pattern"]
        if not isinstance(pattern, str) or ".." in pattern or len(pattern) > 200:
            raise ValueError("requirement.test_pattern is unsafe")
        options = parsed.get("options", {})
        if not isinstance(options, dict) or len(options) > 64:
            raise ValueError("requirement.options is invalid")
        for option_id, option_value in options.items():
            _opaque(option_id, "requirement.option")
            if _PRIVATE_OPTION_PART.search(option_id):
                raise ValueError("requirement option key is private or unsafe")
            if isinstance(option_value, bool):
                continue
            if isinstance(option_value, int) and -1_000_000_000 <= option_value <= 1_000_000_000:
                continue
            if (
                isinstance(option_value, str)
                and option_value
                and option_value == option_value.strip()
                and len(option_value) <= 256
            ):
                continue
            raise ValueError("requirement option value is invalid")
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
    heartbeat_seconds: float
    poll_seconds: float
    retry_backoff_seconds: float
    max_retry_backoff_seconds: float
    max_attempts: int
    testcode_repository: str = "johnny9/mining-qa-testcode"
    environment_allowlist: tuple[str, ...] = ()
    token_environment: str = "MINING_QA_TOKEN"

    @classmethod
    def from_store(cls, store: ConfigStore) -> "CentralSettings":
        document = store.snapshot.document
        coordination = document["coordination"]
        if coordination["mode"] not in {"central", "hybrid"}:
            raise ConfigError("central-once requires coordination.mode: central or hybrid")
        central = coordination["central"]
        token_env = str(central.get("token_env", "MINING_QA_TOKEN"))
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
            heartbeat_seconds=float(central["heartbeat_seconds"]),
            poll_seconds=float(central["poll_seconds"]),
            retry_backoff_seconds=float(central["retry_backoff_seconds"]),
            max_retry_backoff_seconds=float(central["max_retry_backoff_seconds"]),
            max_attempts=int(central["max_attempts"]),
            testcode_repository=str(document["testcode"]["repository"]),
            environment_allowlist=tuple(document["controller"]["environment_allowlist"]),
            token_environment=str(central["token_env"]),
        )


@dataclass(frozen=True, slots=True)
class RunnerPreflight:
    root: Path
    profile: Path
    executable: Path | None
    sha: str
    ref: str


class CentralAgent:
    def __init__(self, settings: CentralSettings, database: OrchestratorDatabase) -> None:
        self.settings = settings
        self.database = database
        self.client = CoordinationClient(settings.base_url, settings.token, settings.timeout)

    def announce(self) -> None:
        nonce = uuid.uuid4().hex
        observed_at = _now()
        capabilities: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
        for binding in self.settings.bindings.values():
            features = tuple(sorted(set(binding["capabilities"])))
            key = (binding["platform_class"], binding["device_model"], features)
            capabilities[key] = {
                "platform_class": binding["platform_class"],
                "device_model": binding["device_model"],
                "features": list(features),
                "aggregate_state": "available",
                "evidence_at": observed_at,
            }
        distinct_capabilities = list(capabilities.values())
        self.client.request(
            "POST",
            f"/api/v2/labs/{quote(self.settings.lab_id)}/heartbeat",
            {
                "contract_version": 2,
                "idempotency_key": f"heartbeat-{nonce}",
                "agent_version": AGENT_VERSION,
                "sent_at": _now(),
                "available_slots": max(0, len(self.settings.bindings) - self.database.central_agent_status()["active_leases"]),
                "capabilities": distinct_capabilities,
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

    def _decline(
        self,
        offer: Mapping[str, Any],
        reason: str,
        *,
        execution: Mapping[str, Any] | None = None,
    ) -> None:
        execution_id = _opaque(offer.get("lab_execution_id"), "offer.lab_execution_id")
        observed = str(offer.get("definition_digest", ""))
        if not _DIGEST.fullmatch(observed):
            observed = "0" * 64
            reason = "invalid_offer"
        claim = None
        if execution is not None and execution.get("state") == "claimed":
            claim = {
                "claim_id": execution["claim_id"],
                "claim_generation": execution["claim_generation"],
                "claim_token": execution["claim_token"],
            }
        self.client.request(
            "POST",
            f"/api/v2/executions/{quote(execution_id)}/decline",
            {
                "contract_version": 2,
                "idempotency_key": f"decline-{_stable_id('id', execution_id)}",
                "lab_id": self.settings.lab_id,
                "observed_definition_digest": observed,
                "claim": claim,
                "reason_code": reason,
            },
        )
        self.database.update_central_execution(execution_id, state="declined")

    def _binding(self, offer: Mapping[str, Any]) -> Mapping[str, Any] | None:
        suite = offer["definition"]["suite"]
        requirements = suite["requirements"]
        catalog_source = suite.get("testcode_catalog")
        if catalog_source is not None and catalog_source["repository"] != self.settings.testcode_repository:
            return None
        items = []
        for requirement in requirements:
            binding = self.settings.bindings.get(requirement["requirement_id"])
            if not binding:
                return None
            if (
                binding["platform_class"] != requirement["platform_class"]
                or binding["device_model"] != requirement["device_model"]
                or not set(requirement["capabilities"]).issubset(binding["capabilities"])
                or offer["platform_class"] != binding["platform_class"]
                or offer["device_model"] != binding["device_model"]
            ):
                return None
            items.append({"requirement": dict(requirement), "binding": dict(binding)})
        if not items or len({item["binding"]["testcode_commit"] for item in items}) != 1:
            return None
        if catalog_source is not None and any(
            item["binding"]["testcode_commit"] != catalog_source["commit_sha"]
            for item in items
        ):
            return None
        return {"version": 1, "items": items}

    @staticmethod
    def _plan_items(
        execution: Mapping[str, Any],
        frozen: Mapping[str, Any],
    ) -> list[tuple[Mapping[str, Any], Mapping[str, Any]]]:
        requirements = execution["offer"]["definition"]["suite"]["requirements"]
        if frozen.get("version") == 1 and isinstance(frozen.get("items"), list):
            raw_items = frozen["items"]
            if len(raw_items) != len(requirements):
                raise ConfigError("central private binding plan does not match the frozen suite")
            items: list[tuple[Mapping[str, Any], Mapping[str, Any]]] = []
            for expected, raw in zip(requirements, raw_items, strict=True):
                if not isinstance(raw, dict):
                    raise ConfigError("central private binding plan is invalid")
                requirement = raw.get("requirement")
                binding = raw.get("binding")
                if (
                    not isinstance(requirement, dict)
                    or not isinstance(binding, dict)
                    or requirement != expected
                ):
                    raise ConfigError("central private binding plan changed after it was frozen")
                items.append((requirement, binding))
            return items
        if len(requirements) != 1:
            raise ConfigError("legacy central binding cannot execute multiple requirements")
        return [(requirements[0], frozen)]

    @staticmethod
    def _assignment_id(
        execution_id: str,
        requirement: Mapping[str, Any],
        requirement_count: int,
    ) -> str:
        identity = (
            execution_id
            if requirement_count == 1
            else f"{execution_id}:{requirement['requirement_id']}"
        )
        return _stable_id("assignment", identity)

    @staticmethod
    def _publishable_attempt(attempt: Mapping[str, Any]) -> bool:
        pointer = attempt.get("pointer")
        return (
            attempt.get("state") in {"passed", "failed", "error", "skipped"}
            and isinstance(pointer, dict)
            and pointer.get("contract_version") == 2
            and isinstance(pointer.get("publishers"), list)
            and isinstance(pointer.get("run_id"), str)
        )

    @staticmethod
    def _repository_from_remote(remote: str) -> str | None:
        value = remote.strip()
        scp = re.fullmatch(
            r"(?:[^@]+@)?github\.com:(?P<path>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?)",
            value,
        )
        if scp:
            path = scp.group("path")
        else:
            parsed = urlsplit(value)
            if (
                parsed.hostname != "github.com"
                or parsed.password
                or parsed.username not in {None, "git"}
            ):
                return None
            path = parsed.path.lstrip("/")
        if path.endswith(".git"):
            path = path[:-4]
        return path if _REPOSITORY.fullmatch(path) else None

    def _preflight(self, binding: Mapping[str, Any]) -> RunnerPreflight:
        root = Path(str(binding["testcode_root"])).resolve()
        profile = Path(str(binding["profile"])).resolve()
        if not root.is_dir() or not (root / ".git").exists():
            raise ConfigError("bound testcode checkout is unavailable")
        if not profile.is_file():
            raise ConfigError("bound runner profile is unavailable")
        try:
            sha, ref = self._testcode_identity(root)
            remote = subprocess.run(
                ["git", "config", "--get", "remote.origin.url"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigError("bound testcode checkout provenance is unavailable") from exc
        if sha != binding["testcode_commit"]:
            raise ConfigError("bound testcode checkout does not match its trusted commit")
        if self._repository_from_remote(remote) != self.settings.testcode_repository:
            raise ConfigError("bound testcode checkout origin does not match trusted repository")
        execution = str(binding["execution"])
        if execution == "mock":
            mock_env = str(binding["mock_base_url_env"])
            mock_url = os.environ.get(mock_env, "").strip()
            if urlsplit(mock_url).hostname not in {"127.0.0.1", "::1", "localhost"}:
                raise ConfigError("central simulation binding requires a loopback mock device")
            return RunnerPreflight(root, profile, None, sha, ref)
        try:
            dirty = subprocess.run(
                ["git", "status", "--porcelain", "--untracked-files=no"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigError("bound testcode checkout status is unavailable") from exc
        if dirty:
            raise ConfigError("bound hardware testcode checkout has tracked modifications")
        executable = Path(str(binding["runner_executable"])).resolve()
        if not executable.is_file() or not os.access(executable, os.X_OK):
            raise ConfigError("bound hardware runner executable is unavailable")
        if executable == Path(sys.executable).resolve():
            raise ConfigError("hardware runner must not reuse the orchestrator interpreter")
        return RunnerPreflight(root, profile, executable, sha, ref)

    def _runner_environment(self) -> dict[str, str]:
        allowed = set(_DEFAULT_RUNNER_ENVIRONMENT)
        allowed.update(self.settings.environment_allowlist)
        allowed.difference_update(_CONTRACT_ENVIRONMENT)
        allowed.discard("MINING_QA_TOKEN")
        allowed.discard(self.settings.token_environment)
        environment = {
            key: value for key, value in os.environ.items() if key in allowed
        }
        environment["MINING_QA_TOKEN"] = self.settings.token
        return environment

    @staticmethod
    def _claim_expired(execution: Mapping[str, Any]) -> bool:
        raw = execution.get("claim_expires_at")
        if not isinstance(raw, str) or not raw:
            return True
        try:
            expires_at = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= datetime.now(UTC)

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
        renewal_cursor = hashlib.sha256(
            str(execution.get("claim_expires_at") or "unobserved").encode()
        ).hexdigest()[:16]
        response = self.client.request(
            "POST",
            f"/api/v2/executions/{quote(str(execution['lab_execution_id']))}/renew",
            {
                "contract_version": 2,
                "idempotency_key": (
                    f"renew-{_stable_id('id', str(execution['lab_execution_id']))}-"
                    f"{execution['claim_generation']}-{renewal_cursor}"
                ),
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

    @staticmethod
    def _drain_runner_stream(
        stream: Any,
        path: Path,
        state: dict[str, Any],
        lock: threading.Lock,
    ) -> None:
        with path.open("wb") as output:
            while True:
                chunk = stream.read(64 * 1024)
                if not chunk:
                    break
                with lock:
                    remaining = MAX_RUNNER_OUTPUT_BYTES - int(state["size"])
                    if remaining > 0:
                        captured = chunk[:remaining]
                        output.write(captured)
                        state["size"] += len(captured)
                    if len(chunk) > max(remaining, 0):
                        state["overflow"] = True

    def _run_testcode(
        self,
        execution: Mapping[str, Any],
        binding: Mapping[str, Any],
        behavior: str,
        requirement: Mapping[str, Any] | None = None,
        assignment_id: str | None = None,
    ) -> tuple[dict[str, Any], str, str, str, str]:
        offer = execution["offer"]
        execution_id = str(execution["lab_execution_id"])
        definition = offer["definition"]
        requirements = definition["suite"]["requirements"]
        if requirement is None:
            requirement = requirements[0]
        if assignment_id is None:
            assignment_id = self._assignment_id(
                execution_id,
                requirement,
                len(requirements),
            )
        assignment_attempt_number = (
            len(self.database.central_attempts_for_assignment(assignment_id)) + 1
        )
        global_attempt_number = len(self.database.central_attempts(execution_id)) + 1
        attempt_identity = (
            f"{execution_id}:{global_attempt_number}"
            if len(requirements) == 1
            else f"{assignment_id}:{assignment_attempt_number}"
        )
        attempt_id = _stable_id("attempt", attempt_identity)
        local_run_id = _stable_id("local", execution_id)
        started_at = _now()
        attempt, created = self.database.start_central_attempt(
            execution_id=execution_id,
            assignment_id=assignment_id,
            attempt_id=attempt_id,
            started_at=started_at,
            max_attempts=self.settings.max_attempts,
        )
        if not created:
            raise ConfigError(f"central execution {execution_id} already has a runner attempt")
        target = self._preflight(binding)
        root, profile, sha, ref = target.root, target.profile, target.sha, target.ref
        source = offer["source"]
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
            "attempt": assignment_attempt_number,
            "source": source,
            "testcode": {
                "repository": self.settings.testcode_repository,
                "ref": ref,
                "commit_sha": sha,
            },
        }
        work = (
            self.settings.state_dir
            / "central-artifacts"
            / execution_id
            / f"attempt-{global_attempt_number}"
        )
        work.mkdir(parents=True, exist_ok=True)
        pointer_path = work / "result-pointer.json"
        artifacts_path = work / "runner"
        environment = self._runner_environment()
        environment.update(
            {
                "MINING_QA_TEST_ARTIFACTS": str(artifacts_path),
                "MINING_QA_URL": self.settings.base_url,
                "MINER_TEST_ORCHESTRATION_METADATA": json.dumps(metadata, separators=(",", ":")),
                "MINER_TEST_EXTERNAL_RUN_ID": assignment_id,
                "MINER_TEST_RESULT_POINTER": str(pointer_path),
                "GITHUB_REPOSITORY": str(source["repository"]),
                "GITHUB_SHA": str(source["commit_sha"]),
                "GITHUB_REF_NAME": str(source["ref_name"]),
            }
        )
        module_id = requirement.get("module_id")
        if module_id is not None:
            environment["MINER_TEST_MODULE_OPTIONS"] = json.dumps(
                {
                    "schema_version": 1,
                    "module_id": module_id,
                    "values": requirement.get("options", {}),
                },
                separators=(",", ":"),
            )
        if source["pr_number"] is None:
            environment.pop("MINER_TEST_PR_NUMBER", None)
        else:
            environment["MINER_TEST_PR_NUMBER"] = str(source["pr_number"])
        execution_mode = str(binding["execution"])
        command: list[str]
        if execution_mode == "mock":
            mock_env = str(binding["mock_base_url_env"])
            mock_url = os.environ.get(mock_env, "").strip()
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
            python_paths = [str(root / "src")]
            guard_path = os.environ.get("MINING_QA_NETWORK_GUARD_PATH", "").strip()
            if guard_path:
                python_paths.insert(0, guard_path)
            environment.update(
                {
                    "PYTHONPATH": os.pathsep.join(python_paths),
                    "MINING_QA_MOCK_URL": mock_url,
                    "MINING_QA_INTEGRATION_DEVELOPMENT": "1",
                    "MINER_TEST_PRIVACY_CANARIES": json.dumps(_CANARIES),
                }
            )
            command = [
                sys.executable,
                "-m",
                "miner_testcode",
                "--config",
                str(profile),
                "--pattern",
                str(requirement["test_pattern"]),
            ]
        else:
            if behavior != "pass":
                raise ConfigError("integration behavior cannot be applied to a hardware binding")
            if target.executable is None:
                raise ConfigError("hardware runner executable disappeared after preflight")
            command = [
                str(target.executable),
                "--config",
                str(profile),
                "--pattern",
                str(requirement["test_pattern"]),
            ]
            for device in binding["runner_devices"]:
                command.extend(["--device", str(device)])
        private_process = work / ".private"
        private_process.mkdir(mode=0o700, exist_ok=True)
        stdout_path = private_process / f"attempt-{global_attempt_number}.stdout.raw.log"
        stderr_path = private_process / f"attempt-{global_attempt_number}.stderr.raw.log"
        renewal_errors: list[str] = []
        renewal_interval = max(
            1.0,
            min(float(offer["claim_ttl_seconds"]) / 2.0, 15.0),
        )
        timeout_seconds = float(binding["timeout_seconds"])
        deadline = time.monotonic() + timeout_seconds
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if process.stdout is None or process.stderr is None:
            process.kill()
            process.wait()
            raise ConfigError("runner process did not expose bounded output streams")
        capture_state: dict[str, Any] = {"size": 0, "overflow": False}
        capture_lock = threading.Lock()
        capture_threads = [
            threading.Thread(
                target=self._drain_runner_stream,
                args=(process.stdout, stdout_path, capture_state, capture_lock),
                daemon=True,
            ),
            threading.Thread(
                target=self._drain_runner_stream,
                args=(process.stderr, stderr_path, capture_state, capture_lock),
                daemon=True,
            ),
        ]
        for capture_thread in capture_threads:
            capture_thread.start()
        timed_out = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                process.kill()
                process.wait()
                timed_out = True
                break
            try:
                process.wait(timeout=min(renewal_interval, remaining))
                break
            except subprocess.TimeoutExpired:
                current = self.database.central_execution(execution_id)
                if current is None:
                    renewal_errors.append("central execution disappeared during renewal")
                    continue
                try:
                    self._renew(current)
                except (ConfigError, CoordinationHttpError, OSError, ValueError) as exc:
                    # Coordination loss must not interrupt Testcode cleanup.
                    renewal_errors.append(f"{type(exc).__name__}: {exc}"[:500])
        for capture_thread in capture_threads:
            capture_thread.join(timeout=5)
        if any(capture_thread.is_alive() for capture_thread in capture_threads):
            raise ConfigError("runner output stream did not close after process exit")
        stdout_path.chmod(0o600)
        stderr_path.chmod(0o600)
        stdout_bytes = stdout_path.read_bytes()
        stderr_bytes = stderr_path.read_bytes()
        if timed_out:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
        if capture_state["overflow"]:
            raise ConfigError("runner output exceeded 1 MiB")
        process_log = (stdout_bytes + b"\n" + stderr_bytes).decode(
            "utf-8", errors="replace"
        )
        if renewal_errors:
            process_log += "\nclaim renewal diagnostics: " + "; ".join(
                renewal_errors[:8]
            )
        for canary in _CANARIES:
            process_log = process_log.replace(canary, "<redacted-canary>")
        (work / "runner-process.log").write_text(process_log, encoding="utf-8")
        (work / "runner-process.log").chmod(0o600)
        try:
            raw_pointer = pointer_path.read_bytes()
        except FileNotFoundError as exc:
            raise ConfigError(
                f"runner exited {process.returncode} without a result pointer"
            ) from exc
        if len(raw_pointer) > 64 * 1024:
            raise ConfigError("runner result pointer exceeds 64 KiB")
        pointer = json.loads(raw_pointer)
        if not isinstance(pointer, dict):
            raise ConfigError("runner result pointer is not an object")
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
        publishers = pointer.get("publishers")
        if not isinstance(publishers, list) or not all(
            isinstance(item, dict) for item in publishers
        ):
            raise ConfigError("runner pointer publishers are invalid")
        if not _OPAQUE.fullmatch(str(pointer.get("run_id", ""))):
            raise ConfigError("runner pointer run identity is invalid")
        publisher = next(
            (
                item
                for item in publishers
                if item.get("name") == "mining_qa_status" and item.get("success") is True
            ),
            None,
        )
        if (
            not publisher
            or publisher.get("required") is not True
            or not _OPAQUE.fullmatch(str(publisher.get("result_id", "")))
        ):
            raise ConfigError("runner pointer lacks a published Status child result")
        result_url = urlsplit(str(publisher.get("url", "")))
        status_url = urlsplit(self.settings.base_url)
        if (
            result_url.scheme not in {"http", "https"}
            or result_url.netloc != status_url.netloc
            or result_url.scheme != status_url.scheme
        ):
            raise ConfigError("runner pointer Status child URL has the wrong public origin")
        successful = pointer.get("successful")
        if not isinstance(successful, bool) or successful != (status in {"passed", "skipped"}):
            raise ConfigError("runner pointer success flag disagrees with terminal status")
        completed_at = _now()
        cleanup = (
            "error"
            if execution_mode == "mock" and behavior == "cleanup-restore-rejected"
            else "restored"
            if execution_mode == "mock"
            else "runner-finished"
        )
        self.database.finish_central_attempt(
            attempt_id=attempt_id,
            state=str(status),
            completed_at=completed_at,
            pointer=pointer,
            cleanup_disposition=cleanup,
        )
        return pointer, started_at, completed_at, sha, ref

    def _completion(
        self,
        execution: Mapping[str, Any],
        testcode_sha: str,
        testcode_ref: str,
    ) -> dict[str, Any]:
        offer = execution["offer"]
        definition = offer["definition"]
        attempts = [
            attempt
            for attempt in self.database.central_attempts(
                str(execution["lab_execution_id"])
            )
            if self._publishable_attempt(attempt)
        ]
        if not attempts:
            raise ConfigError("central completion has no publishable module attempts")
        children = []
        for attempt in attempts:
            saved_pointer = attempt["pointer"]
            publisher = next(
                item
                for item in saved_pointer["publishers"]
                if item["name"] == "mining_qa_status" and item.get("success") is True
            )
            children.append(
                {
                    "assignment_id": attempt["assignment_id"],
                    "attempt_id": attempt["attempt_id"],
                    "runner_run_id": saved_pointer["run_id"],
                    "status": saved_pointer["status"],
                    "result_id": publisher["result_id"],
                    "result_url": publisher["url"],
                }
            )
        statuses = {str(child["status"]) for child in children}
        outcome = (
            "error"
            if "error" in statuses
            else "failed"
            if "failed" in statuses
            else "passed"
            if "passed" in statuses
            else "skipped"
        )
        first_pointer = attempts[0]["pointer"]
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
                "local_gate_run_id": first_pointer["correlation"]["local_gate_run_id"],
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
                "outcome": outcome,
                "started_at": min(str(attempt["started_at"]) for attempt in attempts),
                "completed_at": max(str(attempt["completed_at"]) for attempt in attempts),
                "source": offer["source"],
                "testcode": {
                    "repository": self.settings.testcode_repository,
                    "ref": testcode_ref,
                    "commit_sha": testcode_sha,
                },
                "children": children,
                "reason_code": None,
            },
        }

    def _error_completion(
        self,
        execution: Mapping[str, Any],
        *,
        testcode_sha: str,
        testcode_ref: str,
    ) -> dict[str, Any]:
        offer = execution["offer"]
        definition = offer["definition"]
        attempts = self.database.central_attempts(str(execution["lab_execution_id"]))
        if not attempts:
            raise ConfigError("central error completion has no immutable attempt")
        attempt = attempts[-1]
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
                "local_gate_run_id": _stable_id(
                    "local", str(execution["lab_execution_id"])
                ),
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
                "outcome": "error",
                "started_at": attempt["started_at"],
                "completed_at": attempt["completed_at"],
                "source": offer["source"],
                "testcode": {
                    "repository": self.settings.testcode_repository,
                    "ref": testcode_ref,
                    "commit_sha": testcode_sha,
                },
                "children": [],
                "reason_code": "local_execution_error",
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
                self.database.release_central_resources(str(execution["lab_execution_id"]))
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
        self.database.release_central_resources(str(execution["lab_execution_id"]))
        return "completed"

    def _execute_with_lease(
        self,
        execution: Mapping[str, Any],
        binding: Mapping[str, Any],
        *,
        phase: str,
        behavior: str,
    ) -> str:
        execution_id = str(execution["lab_execution_id"])
        items = self._plan_items(execution, binding)
        if phase == "reclaim" or (
            execution["state"] == "claimed" and self._claim_expired(execution)
        ):
            try:
                self._claim(execution, next_generation=True)
            except CoordinationHttpError as exc:
                if exc.status == 409 and exc.body.get("error", {}).get("code") == "claim_expired":
                    self.database.update_central_execution(execution_id, state="conflict")
                    self.database.release_central_resources(execution_id)
                    return "conflict"
                raise
        elif execution["state"] != "claimed":
            self._claim(execution)
        current = self.database.central_execution(execution_id)
        if current is None:
            raise ConfigError("claimed central execution disappeared")
        if phase == "claim-only":
            return "claimed"
        self._renew(current)
        current = self.database.central_execution(execution_id)
        if current is None:
            raise ConfigError("renewed central execution disappeared")
        testcode_sha = str(items[0][1].get("testcode_commit", "0" * 40))
        testcode_ref = "detached"
        for requirement, item_binding in items:
            assignment_id = self._assignment_id(
                execution_id,
                requirement,
                len(items),
            )
            assignment_attempts = self.database.central_attempts_for_assignment(
                assignment_id
            )
            publishable = next(
                (
                    attempt
                    for attempt in reversed(assignment_attempts)
                    if self._publishable_attempt(attempt)
                ),
                None,
            )
            if publishable is not None:
                continue
            trusted_target = self._preflight(item_binding)
            testcode_sha = trusted_target.sha
            testcode_ref = trusted_target.ref
            if assignment_attempts and (
                item_binding["execution"] == "hardware"
                or len(assignment_attempts) >= self.settings.max_attempts
            ):
                completion = self._error_completion(
                    current,
                    testcode_sha=testcode_sha,
                    testcode_ref=testcode_ref,
                )
                self.database.enqueue_central_completion(
                    execution_id=execution_id,
                    idempotency_key=str(completion["idempotency_key"]),
                    body=completion,
                )
                return self._flush(current)
            while True:
                try:
                    if len(items) == 1:
                        run = self._run_testcode(current, item_binding, behavior)
                    else:
                        run = self._run_testcode(
                            current,
                            item_binding,
                            behavior,
                            requirement,
                            assignment_id,
                        )
                    _, _, _, testcode_sha, testcode_ref = run
                    break
                except (ConfigError, OSError, subprocess.SubprocessError, ValueError) as exc:
                    hardware = item_binding["execution"] == "hardware"
                    self.database.fail_running_central_attempt(
                        execution_id,
                        str(exc),
                        cleanup_disposition="uncertain" if hardware else "error",
                    )
                    assignment_attempts = (
                        self.database.central_attempts_for_assignment(assignment_id)
                    )
                    if hardware or len(assignment_attempts) >= self.settings.max_attempts:
                        completion = self._error_completion(
                            current,
                            testcode_sha=testcode_sha,
                            testcode_ref=testcode_ref,
                        )
                        self.database.enqueue_central_completion(
                            execution_id=execution_id,
                            idempotency_key=str(completion["idempotency_key"]),
                            body=completion,
                        )
                        return self._flush(current)
                    delay = min(
                        self.settings.retry_backoff_seconds
                        * (2 ** (len(assignment_attempts) - 1)),
                        self.settings.max_retry_backoff_seconds,
                    )
                    time.sleep(delay)
        completion = self._completion(
            current,
            testcode_sha,
            testcode_ref,
        )
        self.database.enqueue_central_completion(
            execution_id=execution_id,
            idempotency_key=str(completion["idempotency_key"]),
            body=completion,
        )
        return self._flush(current)

    def process(
        self,
        *,
        phase: str,
        behavior: str,
        replay_from_zero: bool = False,
        announce: bool = True,
    ) -> list[str]:
        if announce:
            self.announce()
        self.pull(replay_from_zero=replay_from_zero)
        results: list[str] = []
        for saved in self.database.pending_central_executions(self.settings.lab_id):
            offer = saved["offer"]
            execution = self.database.central_execution(str(saved["lab_execution_id"]))
            if execution is None:
                raise ConfigError("persisted central execution disappeared")
            outbox = self.database.central_outbox(str(execution["lab_execution_id"]))
            if outbox:
                results.append(self._flush(execution))
                continue
            try:
                validated = validate_offer(offer, self.settings.lab_id)
            except (TypeError, ValueError):
                self._decline(
                    offer,
                    "definition_mismatch"
                    if set(offer) == set(_OFFER_KEYS)
                    else "invalid_offer",
                    execution=execution,
                )
                results.append("declined")
                continue
            binding_plan = execution.get("binding") or self._binding(validated)
            if behavior == "decline-no-safe-binding" or binding_plan is None:
                self._decline(validated, "no_safe_binding", execution=execution)
                results.append("declined")
                continue
            try:
                binding_plan = self.database.freeze_central_binding(
                    str(execution["lab_execution_id"]), binding_plan
                )
                items = self._plan_items(execution, binding_plan)
            except ValueError as exc:
                raise ConfigError("central private binding snapshot is invalid") from exc
            try:
                for _, item_binding in items:
                    self._preflight(item_binding)
            except ConfigError:
                attempts = self.database.central_attempts(
                    str(execution["lab_execution_id"])
                )
                if attempts:
                    # Recovery uses the frozen snapshot and durable attempt below;
                    # it must not be reclassified from mutable checkout availability.
                    pass
                else:
                    self._decline(validated, "no_safe_binding", execution=execution)
                    results.append("declined")
                    continue
            attempts = self.database.central_attempts(str(execution["lab_execution_id"]))
            if attempts and attempts[-1]["state"] == "running":
                self.database.fail_running_central_attempt(
                    str(execution["lab_execution_id"]),
                    "agent restarted while the runner attempt was active",
                    cleanup_disposition=(
                        "uncertain"
                        if any(
                            item_binding["execution"] == "hardware"
                            for _, item_binding in items
                        )
                        else "error"
                    ),
                )
                attempts = self.database.central_attempts(str(execution["lab_execution_id"]))
            execution_id = str(execution["lab_execution_id"])
            lease_owner_id = (
                self._assignment_id(execution_id, items[0][0], 1)
                if len(items) == 1
                else _stable_id("lease", execution_id)
            )
            resources = sorted(
                {
                    str(resource)
                    for _, item_binding in items
                    for resource in item_binding["resources"]
                }
            )
            if not self.database.acquire_central_resources(
                execution_id,
                lease_owner_id,
                resources,
            ):
                self._decline(
                    validated,
                    "local_capacity_changed",
                    execution=execution,
                )
                results.append("declined")
                continue
            try:
                results.append(
                    self._execute_with_lease(
                        execution,
                        binding_plan,
                        phase=phase,
                        behavior=behavior,
                    )
                )
            except Exception:
                self.database.release_central_resources(
                    str(execution["lab_execution_id"])
                )
                raise
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


def register_central_lab(
    store: ConfigStore,
    *,
    public_label: str,
    agent_environment_file: Path,
) -> dict[str, str]:
    document = store.snapshot.document
    if document["coordination"]["mode"] not in {"central", "hybrid"}:
        raise ConfigError("central registration requires coordination.mode: central or hybrid")
    label = public_label.strip()
    if not label or len(label) > 80 or any(ord(character) < 32 for character in label):
        raise ConfigError("central public label must be 1-80 printable characters")
    if not agent_environment_file.is_absolute() or agent_environment_file == Path("/"):
        raise ConfigError("central agent environment file must be an absolute non-root path")
    if agent_environment_file.is_symlink():
        raise ConfigError("central agent environment file must not be a symbolic link")
    destination = agent_environment_file.resolve()
    if not destination.parent.is_dir():
        raise ConfigError("central agent environment file parent does not exist")
    if destination.exists() or destination.is_symlink():
        raise ConfigError("central agent environment file already exists")
    central = document["coordination"]["central"]
    token_environment = str(central["token_env"])
    lab_token = os.environ.get(token_environment, "").strip()
    if not lab_token or not _AGENT_TOKEN.fullmatch(lab_token):
        raise ConfigError(
            f"app-issued Lab token environment is not set or invalid: {token_environment}"
        )
    lab_id = str(central["lab_id"])
    body = {
        "contract_version": 2,
        "idempotency_key": _stable_id(
            "register", f"{lab_id}:{label}:{AGENT_VERSION}"
        ),
        "lab_id": lab_id,
        "public_lab_label": label,
        "agent_version": AGENT_VERSION,
        "supported_coordination_versions": [2],
        "supported_orchestration_versions": [1, 2],
    }
    response = CoordinationClient(
        str(central["base_url"]),
        lab_token,
        float(central["request_timeout_seconds"]),
    ).request("POST", "/api/v2/labs/register", body)
    if (
        response.get("contract_version") != 2
        or response.get("lab_id") != lab_id
        or response.get("credential_state") != "bound"
    ):
        raise ConfigError("central registration did not bind the app-issued Lab token")
    try:
        registration_id = _opaque(
            response.get("registration_id"), "registration.registration_id"
        )
        issued_at = _timestamp(response.get("issued_at"), "registration.issued_at")
    except ValueError as exc:
        raise ConfigError("central registration returned invalid public metadata") from exc
    descriptor = os.open(
        destination,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(f"{token_environment}={lab_token}\n")
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    destination.chmod(0o600)
    return {
        "lab_id": lab_id,
        "registration_id": registration_id,
        "issued_at": issued_at,
        "agent_environment_file": str(destination),
    }


def run_central_forever(
    store: ConfigStore,
    database: OrchestratorDatabase,
    *,
    stop: threading.Event | None = None,
    max_cycles: int | None = None,
) -> int:
    """Run bounded coordination cycles with persisted pause and retry state."""
    stop = stop or threading.Event()
    settings = CentralSettings.from_store(store)
    agent = CentralAgent(settings, database)
    initial_status = database.central_agent_status()
    failures = int(initial_status["consecutive_failures"])
    cycles = 0
    next_heartbeat_at = 0.0
    while not stop.is_set() and (max_cycles is None or cycles < max_cycles):
        status = database.central_agent_status()
        if status["paused"]:
            if max_cycles is not None:
                return cycles
            stop.wait(min(settings.poll_seconds, 2.0))
            continue
        retry_at = status.get("next_retry_at")
        if retry_at is not None and float(retry_at) > time.time():
            stop.wait(min(float(retry_at) - time.time(), 2.0))
            continue
        error: str | None = None
        delay = settings.poll_seconds
        try:
            now = time.monotonic()
            announce = now >= next_heartbeat_at
            agent.process(phase="run", behavior="pass", announce=announce)
            if announce:
                next_heartbeat_at = now + settings.heartbeat_seconds
            failures = 0
        except (ConfigError, CoordinationHttpError, OSError, ValueError) as exc:
            failures += 1
            error = f"{type(exc).__name__}: {exc}"
            delay = min(
                settings.retry_backoff_seconds * (2 ** (failures - 1)),
                settings.max_retry_backoff_seconds,
            )
        cycles += 1
        next_retry = time.time() + delay if error else None
        database.record_central_agent_cycle(
            error=error,
            consecutive_failures=failures,
            next_retry_at=next_retry,
        )
        if max_cycles is None or cycles < max_cycles:
            stop.wait(delay)
    return cycles
