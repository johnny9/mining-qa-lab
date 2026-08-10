from __future__ import annotations

import json
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .errors import LabError

MAX_JSON_RESPONSE_BYTES = 4 * 1024 * 1024


class PublishError(LabError):
    """A Mining QA Status gate publication failed."""


class HttpTransport(Protocol):
    def json_request(
        self,
        method: str,
        url: str,
        body: Mapping[str, Any],
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
    ) -> dict[str, Any]: ...


class UrlLibTransport:
    """Bounded stdlib JSON transport that never includes tokens in errors."""

    def json_request(
        self,
        method: str,
        url: str,
        body: Mapping[str, Any],
        *,
        token: str | None = None,
        headers: Mapping[str, str] | None = None,
        timeout: float = 20.0,
    ) -> dict[str, Any]:
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            **dict(headers or {}),
        }
        if token:
            request_headers["Authorization"] = f"Bearer {token}"
        request = Request(
            url,
            data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
            headers=request_headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read(MAX_JSON_RESPONSE_BYTES + 1)
                if len(payload) > MAX_JSON_RESPONSE_BYTES:
                    raise PublishError(f"{method} {url} response exceeded 4 MiB")
        except HTTPError as exc:
            detail = exc.read(1000).decode("utf-8", errors="replace")
            raise PublishError(
                f"{method} {url} returned HTTP {exc.code}: {detail}"
            ) from exc
        except (URLError, OSError, TimeoutError) as exc:
            raise PublishError(f"{method} {url} failed: {exc}") from exc
        if not payload:
            return {}
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise PublishError(f"{method} {url} returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise PublishError(f"{method} {url} returned non-object JSON")
        return value
