from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .errors import ConfigError


_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GATE_KEY = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_COMMIT = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_MAX_RESPONSE_BYTES = 1024 * 1024


class QaStatusRerunError(ConfigError):
    pass


def _uuid(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise QaStatusRerunError(f"QA Status rerun response has invalid {field}")
    try:
        return str(uuid.UUID(value))
    except ValueError as exc:
        raise QaStatusRerunError(
            f"QA Status rerun response has invalid {field}"
        ) from exc


def _claim(payload: object) -> dict[str, Any] | None:
    if not isinstance(payload, dict) or "request" not in payload:
        raise QaStatusRerunError("QA Status rerun claim returned an invalid response")
    value = payload["request"]
    if value is None:
        return None
    if not isinstance(value, dict):
        raise QaStatusRerunError("QA Status rerun claim returned an invalid request")

    request_id = _uuid(value.get("id"), "request ID")
    claim_token = _uuid(value.get("claim_token"), "claim token")
    gate_run_id = _uuid(value.get("gate_run_id"), "gate run ID")
    external_run_id = value.get("external_run_id")
    repository = value.get("repository")
    gate_key = value.get("gate_key")
    commit_sha = value.get("commit_sha")
    mode = value.get("mode")
    assignment_ids = value.get("assignment_ids")
    if not isinstance(external_run_id, str) or not 1 <= len(external_run_id) <= 255:
        raise QaStatusRerunError("QA Status rerun response has invalid external run ID")
    if not isinstance(repository, str) or not _REPOSITORY.fullmatch(repository):
        raise QaStatusRerunError("QA Status rerun response has invalid repository")
    if not isinstance(gate_key, str) or not _GATE_KEY.fullmatch(gate_key):
        raise QaStatusRerunError("QA Status rerun response has invalid gate key")
    if not isinstance(commit_sha, str) or not _COMMIT.fullmatch(commit_sha):
        raise QaStatusRerunError("QA Status rerun response has invalid commit")
    if mode not in {"all", "assignments"}:
        raise QaStatusRerunError("QA Status rerun response has invalid mode")
    if (
        not isinstance(assignment_ids, list)
        or len(assignment_ids) > 100
        or any(
            not isinstance(item, str) or not 1 <= len(item) <= 255
            for item in assignment_ids
        )
    ):
        raise QaStatusRerunError("QA Status rerun response has invalid assignments")
    if mode == "all" and assignment_ids:
        raise QaStatusRerunError("QA Status all-mode rerun included assignments")
    if mode == "assignments" and not assignment_ids:
        raise QaStatusRerunError("QA Status selected rerun omitted assignments")

    return {
        "id": request_id,
        "claim_token": claim_token,
        "gate_run_id": gate_run_id,
        "external_run_id": external_run_id,
        "repository": repository,
        "gate_key": gate_key,
        "commit_sha": commit_sha,
        "mode": mode,
        "assignment_ids": list(dict.fromkeys(assignment_ids)),
    }


class QaStatusRerunClient:
    """Lease rerun intent; local validation remains authoritative."""

    def __init__(self, *, timeout: float = 20.0) -> None:
        self.timeout = timeout

    def _post(
        self, config: Mapping[str, Any], path: str, payload: Mapping[str, Any]
    ) -> object:
        base_url = str(config.get("base_url") or "").rstrip("/")
        token_env = str(config.get("token_env") or "MINING_QA_TOKEN")
        token = os.environ.get(token_env, "").strip()
        if not base_url or not token:
            raise QaStatusRerunError(
                f"QA Status rerun polling requires qa_status.base_url and environment {token_env}"
            )
        encoded = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
        request = Request(
            f"{base_url}{path}",
            data=encoded,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "mining-qa-lab",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                response_body = response.read(_MAX_RESPONSE_BYTES + 1)
                if len(response_body) > _MAX_RESPONSE_BYTES:
                    raise QaStatusRerunError("QA Status rerun response exceeded 1 MiB")
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise QaStatusRerunError(
                f"QA Status rerun request returned HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise QaStatusRerunError(f"QA Status rerun request failed: {exc}") from exc
        try:
            return json.loads(response_body)
        except json.JSONDecodeError as exc:
            raise QaStatusRerunError(
                "QA Status rerun request returned invalid JSON"
            ) from exc

    def claim(
        self, config: Mapping[str, Any], targets: list[Mapping[str, str]]
    ) -> dict[str, Any] | None:
        return _claim(
            self._post(config, "/api/v1/lab/rerun-requests/claim", {"targets": targets})
        )

    def resolve(
        self,
        config: Mapping[str, Any],
        request_id: str,
        claim_token: str,
        outcome: str,
        detail: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "claim_token": claim_token,
            "outcome": outcome,
        }
        if detail:
            payload["detail"] = detail[:1000]
        response = self._post(
            config,
            f"/api/v1/lab/rerun-requests/{quote(request_id, safe='')}/resolve",
            payload,
        )
        if (
            not isinstance(response, dict)
            or not isinstance(response.get("request"), dict)
            or response["request"].get("state") != outcome
        ):
            raise QaStatusRerunError(
                "QA Status rerun resolution returned an invalid response"
            )
