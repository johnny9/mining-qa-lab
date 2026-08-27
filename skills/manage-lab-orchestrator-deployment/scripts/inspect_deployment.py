#!/usr/bin/env python3
"""Inspect a miner-orchestrator systemd deployment without changing it."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

MAX_OUTPUT_BYTES = 64 * 1024
UNIT_PATTERN = re.compile(r"[A-Za-z0-9_.@:-]+\Z")


class InspectionError(RuntimeError):
    pass


def _bounded_text(value: str) -> str:
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) > MAX_OUTPUT_BYTES:
        encoded = encoded[-MAX_OUTPUT_BYTES:]
    return encoded.decode("utf-8", errors="replace")


def inspect_unit(unit: str, timeout: float) -> dict[str, str]:
    if not UNIT_PATTERN.fullmatch(unit):
        raise InspectionError("unit name contains unsupported characters")
    try:
        result = subprocess.run(
            [
                "systemctl",
                "--user",
                "show",
                unit,
                "--property=LoadState,ActiveState,SubState,FragmentPath,ExecMainStatus",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InspectionError(f"systemd inspection failed: {type(exc).__name__}: {exc}") from exc
    output = _bounded_text(result.stdout or "")
    if result.returncode != 0:
        raise InspectionError(
            f"systemctl show failed with exit {result.returncode}: {output.strip()}"
        )
    values: dict[str, str] = {}
    for line in output.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            values[key] = value
    required = {"LoadState", "ActiveState", "SubState", "FragmentPath", "ExecMainStatus"}
    if not required.issubset(values):
        raise InspectionError("systemctl show returned incomplete service properties")
    return values


def validate_config(executable: Path, config: Path, timeout: float) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(executable), "--config", str(config), "validate"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InspectionError(f"config validation failed to start: {type(exc).__name__}: {exc}") from exc
    output = _bounded_text(result.stdout or "").strip()
    if result.returncode != 0:
        raise InspectionError(
            f"config validation failed with exit {result.returncode}: {output}"
        )
    if not re.fullmatch(r"[0-9a-f]{64}", output):
        raise InspectionError("config validation did not return one SHA-256 digest")
    return {"valid": True, "revision": output}


def inspect_health(url: str, timeout: float) -> dict[str, Any]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise InspectionError("health URL must be HTTP(S) with a host")
    if parsed.username is not None or parsed.password is not None:
        raise InspectionError("health URL must not contain credentials")
    request = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(request, timeout=timeout) as response:
            length = response.headers.get("Content-Length")
            if length is not None and int(length) > MAX_OUTPUT_BYTES:
                raise InspectionError("health response exceeds 64 KiB")
            payload = response.read(MAX_OUTPUT_BYTES + 1)
    except InspectionError:
        raise
    except (OSError, ValueError) as exc:
        raise InspectionError(f"health request failed: {type(exc).__name__}: {exc}") from exc
    if len(payload) > MAX_OUTPUT_BYTES:
        raise InspectionError("health response exceeds 64 KiB")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InspectionError(f"health response is not valid JSON: {exc}") from exc
    if not isinstance(value, dict) or value.get("status") != "ok":
        raise InspectionError("health response does not report status ok")
    revision = value.get("config_revision")
    queued = value.get("queued_assignments")
    running = value.get("running_assignments")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{64}", revision):
        raise InspectionError("health response has no valid config revision")
    for name, count in (("queued_assignments", queued), ("running_assignments", running)):
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise InspectionError(f"health response has invalid {name}")
    result = {
        "status": "ok",
        "config_revision": revision,
        "queued_assignments": queued,
        "running_assignments": running,
    }
    central = value.get("central")
    if central is not None:
        if not isinstance(central, dict) or not isinstance(central.get("paused"), bool):
            raise InspectionError("health response has invalid central agent state")
        central_result = {"paused": central["paused"]}
        for name in ("active_leases", "pending_executions", "pending_outbox"):
            count = central.get(name)
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                raise InspectionError(f"health response has invalid central.{name}")
            central_result[name] = count
        result["central"] = central_result
    return result


def inspect(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    report: dict[str, Any] = {"unit": args.unit, "issues": []}
    issues: list[str] = report["issues"]
    try:
        service = inspect_unit(args.unit, args.timeout)
        report["service"] = service
    except InspectionError as exc:
        service = {}
        issues.append(str(exc))

    if args.orchestrator is not None:
        try:
            report["config"] = validate_config(
                Path(args.orchestrator), Path(args.config), args.timeout
            )
        except InspectionError as exc:
            issues.append(str(exc))

    try:
        health = inspect_health(args.health_url, args.timeout)
        report["health"] = health
    except InspectionError as exc:
        health = {}
        issues.append(str(exc))

    service_active = service.get("LoadState") == "loaded" and service.get("ActiveState") == "active"
    running = health.get("running_assignments")
    central = health.get("central")
    central_idle = central is None or (
        central.get("paused") is True and central.get("active_leases") == 0
    )
    safe_to_restart = (
        service_active
        and health.get("status") == "ok"
        and running == 0
        and central_idle
    )
    report["safe_to_restart"] = safe_to_restart
    if not service_active:
        issues.append("service is not loaded and active")
    if args.require_idle and not safe_to_restart:
        issues.append("deployment is not observed idle and healthy")
    return report, not issues


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--unit", default="miner-orchestrator.service")
    parser.add_argument(
        "--health-url",
        default="http://127.0.0.1:8765/api/v1/health",
    )
    parser.add_argument("--orchestrator")
    parser.add_argument("--config")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--require-idle", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if (args.orchestrator is None) != (args.config is None):
        parser.error("--orchestrator and --config must be supplied together")
    if not 0 < args.timeout <= 60:
        parser.error("--timeout must be greater than zero and at most 60 seconds")
    report, successful = inspect(args)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if successful else 1


if __name__ == "__main__":
    raise SystemExit(main())
