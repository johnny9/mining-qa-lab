from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import subprocess
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.request import Request as UrlRequest, urlopen

import yaml
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from .errors import ConfigError
from .config import ConfigSnapshot, ConfigStore
from .database import OrchestratorDatabase
from .engine import OrchestratorEngine
from .ui import render_page


def _state_dir(store: ConfigStore) -> Path:
    value = Path(store.snapshot.document["controller"]["state_dir"])
    return value if value.is_absolute() else (store.source.parent / value).resolve()


def api_token(store: ConfigStore) -> str:
    controller = store.snapshot.document["controller"]
    token_env = str(controller.get("api_token_env") or "MINER_ORCHESTRATOR_API_TOKEN")
    configured = os.environ.get(token_env, "").strip()
    if configured:
        return configured
    token_path = _state_dir(store) / "api-token"
    if token_path.exists():
        return token_path.read_text(encoding="utf-8").strip()
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    descriptor = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(token + "\n")
    return token


def _revision(if_match: str | None) -> str | None:
    if not if_match:
        return None
    return if_match.strip().strip('"').removeprefix("config-")


def _snapshot_response(snapshot: ConfigSnapshot, *, include_document: bool = True) -> Response:
    payload: dict[str, Any] = {
        "revision": snapshot.revision,
        "loaded_at": snapshot.loaded_at,
        "source": str(snapshot.source),
    }
    if include_document:
        payload["config"] = snapshot.document
    return JSONResponse(payload, headers={"ETag": snapshot.etag})


def create_app(
    store: ConfigStore,
    database: OrchestratorDatabase,
    engine: OrchestratorEngine | None = None,
) -> FastAPI:
    engine = engine or OrchestratorEngine(store, database)
    token = (
        api_token(store)
        if store.snapshot.document["controller"].get("auth_mode", "bearer") == "bearer"
        else None
    )
    stop = asyncio.Event()

    async def loop() -> None:
        interval = float(store.snapshot.document["controller"]["poll_seconds"])
        last_poll = 0.0
        while not stop.is_set():
            try:
                if store.snapshot.document["coordination"]["mode"] == "central":
                    from .central import run_central_forever

                    await asyncio.to_thread(
                        run_central_forever,
                        store,
                        database,
                        max_cycles=1,
                    )
                    central_interval = float(
                        store.snapshot.document["coordination"]["central"]["poll_seconds"]
                    )
                    await asyncio.wait_for(stop.wait(), timeout=central_interval)
                    continue
                now = asyncio.get_running_loop().time()
                if now - last_poll >= interval:
                    await asyncio.to_thread(engine.poll)
                    last_poll = now
                while await asyncio.to_thread(engine.tick):
                    pass
            except TimeoutError:
                continue
            except Exception as exc:  # background health is exposed through logs
                import logging

                logging.getLogger(__name__).exception("orchestrator loop failed: %s", exc)
            try:
                await asyncio.wait_for(stop.wait(), timeout=2)
            except TimeoutError:
                pass

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.recover_interrupted()
        task = asyncio.create_task(loop())
        yield
        stop.set()
        await task

    app = FastAPI(
        title="Miner Test Orchestrator",
        version="1.0.0",
        description="Configure repository-triggered mining test gates and lab devices.",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def restrict_network(request: Request, call_next: Callable[..., Any]) -> Response:
        networks = store.snapshot.document["controller"].get("allowed_networks", [])
        if networks:
            client_host = request.client.host if request.client else ""
            try:
                client_address = ip_address(client_host)
            except ValueError:
                return JSONResponse(
                    status_code=403, content={"detail": "client network is not allowed"}
                )
            if not any(
                client_address in ip_network(network, strict=False) for network in networks
            ):
                return JSONResponse(
                    status_code=403, content={"detail": "client network is not allowed"}
                )
        return await call_next(request)

    async def authorize(authorization: str | None = Header(default=None)) -> None:
        if store.snapshot.document["controller"].get("auth_mode", "bearer") == "none":
            return
        supplied = ""
        if authorization and authorization.startswith("Bearer "):
            supplied = authorization[7:]
        expected_token = token or api_token(store)
        if not supplied or not hmac.compare_digest(supplied, expected_token):
            raise HTTPException(status_code=401, detail="valid local bearer token required")

    def expected(if_match: str | None) -> str | None:
        revision = _revision(if_match)
        if revision is None:
            raise HTTPException(status_code=428, detail="If-Match configuration ETag is required")
        return revision

    def mutation(call: Callable[[], ConfigSnapshot]) -> Response:
        try:
            return _snapshot_response(call())
        except ConfigError as exc:
            status = 412 if "revision does not match" in str(exc) else 422
            raise HTTPException(status_code=status, detail=str(exc)) from exc

    @app.get("/api/v1/health")
    async def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "config_revision": store.snapshot.revision,
            "queued_assignments": len(database.assignments(status="queued")),
            "running_assignments": len(database.assignments(status="running")),
            "central": database.central_agent_status()
            if store.snapshot.document["coordination"]["mode"] == "central"
            else None,
        }

    @app.get("/api/v1/central/status", dependencies=[Depends(authorize)])
    async def central_status() -> dict[str, Any]:
        if store.snapshot.document["coordination"]["mode"] != "central":
            raise HTTPException(status_code=409, detail="central coordination mode is not enabled")
        return database.central_agent_status()

    @app.post("/api/v1/central/pause", dependencies=[Depends(authorize)])
    async def pause_central() -> dict[str, Any]:
        if store.snapshot.document["coordination"]["mode"] != "central":
            raise HTTPException(status_code=409, detail="central coordination mode is not enabled")
        return database.set_central_agent_paused(True)

    @app.post("/api/v1/central/resume", dependencies=[Depends(authorize)])
    async def resume_central() -> dict[str, Any]:
        if store.snapshot.document["coordination"]["mode"] != "central":
            raise HTTPException(status_code=409, detail="central coordination mode is not enabled")
        return database.set_central_agent_paused(False)

    @app.get("/api/v1/config")
    async def get_config() -> Response:
        return _snapshot_response(store.snapshot)

    @app.get("/api/v1/config/yaml")
    async def get_config_yaml() -> Response:
        return Response(
            yaml.safe_dump(store.snapshot.document, sort_keys=False),
            media_type="application/yaml",
            headers={"ETag": store.snapshot.etag},
        )

    @app.post("/api/v1/config/validate")
    async def validate_config(request: Request) -> Response:
        try:
            document = await request.json()
            return _snapshot_response(store.validate(document))
        except (ConfigError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.put("/api/v1/config", dependencies=[Depends(authorize)])
    async def replace_config(request: Request, if_match: str | None = Header(default=None)) -> Response:
        try:
            document = await request.json()
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="request body must be JSON") from exc
        return mutation(
            lambda: store.replace(document, expected_revision=expected(if_match))
        )

    @app.put("/api/v1/config/yaml", dependencies=[Depends(authorize)])
    async def replace_config_yaml(
        request: Request, if_match: str | None = Header(default=None)
    ) -> Response:
        try:
            document = yaml.safe_load((await request.body()).decode("utf-8"))
        except (UnicodeDecodeError, yaml.YAMLError) as exc:
            raise HTTPException(status_code=422, detail=f"invalid YAML: {exc}") from exc
        if not isinstance(document, dict):
            raise HTTPException(status_code=422, detail="YAML root must be an object")
        return mutation(
            lambda: store.replace(document, expected_revision=expected(if_match))
        )

    @app.post("/api/v1/config/reload", dependencies=[Depends(authorize)])
    async def reload_config() -> Response:
        try:
            return _snapshot_response(store.reload())
        except ConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/config/revisions")
    async def revisions() -> dict[str, Any]:
        directory = store.source.parent / ".orchestrator-backups"
        return {
            "active": store.snapshot.revision,
            "backups": [item.name for item in sorted(directory.glob("*.bak"), reverse=True)]
            if directory.exists()
            else [],
        }

    @app.get("/api/v1/config/revisions/{backup_name}")
    async def revision(backup_name: str) -> dict[str, Any]:
        if Path(backup_name).name != backup_name or not backup_name.endswith(".bak"):
            raise HTTPException(status_code=404, detail="configuration revision not found")
        path = store.source.parent / ".orchestrator-backups" / backup_name
        if not path.is_file():
            raise HTTPException(status_code=404, detail="configuration revision not found")
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            snapshot = store.validate(document)
        except (ConfigError, yaml.YAMLError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {"name": backup_name, "revision": snapshot.revision, "config": document}

    def section_values(section: str) -> Mapping[str, Any]:
        if section in {"hosts", "devices", "setups"}:
            return store.snapshot.document["lab"][section]
        return store.snapshot.document[section]

    def install_resource_routes(path: str, section: str) -> None:
        @app.get(f"/api/v1/{path}", name=f"list_{section}")
        async def list_resources() -> Response:
            return JSONResponse(
                {section: section_values(section), "revision": store.snapshot.revision},
                headers={"ETag": store.snapshot.etag},
            )

        @app.get(f"/api/v1/{path}/{{resource_id}}", name=f"get_{section}")
        async def get_resource(resource_id: str) -> Response:
            value = section_values(section).get(resource_id)
            if value is None:
                raise HTTPException(status_code=404, detail="resource not found")
            return JSONResponse(
                {"id": resource_id, "value": value, "revision": store.snapshot.revision},
                headers={"ETag": store.snapshot.etag},
            )

        @app.post(
            f"/api/v1/{path}",
            name=f"create_{section}",
            dependencies=[Depends(authorize)],
        )
        async def create_resource(
            request: Request, if_match: str | None = Header(default=None)
        ) -> Response:
            body = await request.json()
            resource_id = body.get("id") if isinstance(body, dict) else None
            value = body.get("value") if isinstance(body, dict) else None
            if not isinstance(resource_id, str) or not isinstance(value, dict):
                raise HTTPException(status_code=422, detail="body requires id and value")
            return mutation(
                lambda: store.mutate_resource(
                    section,
                    resource_id,
                    value,
                    expected_revision=expected(if_match),
                    create_only=True,
                )
            )

        @app.patch(
            f"/api/v1/{path}/{{resource_id}}",
            name=f"update_{section}",
            dependencies=[Depends(authorize)],
        )
        async def update_resource(
            resource_id: str,
            request: Request,
            if_match: str | None = Header(default=None),
        ) -> Response:
            value = await request.json()
            if not isinstance(value, dict):
                raise HTTPException(status_code=422, detail="body must be an object")
            return mutation(
                lambda: store.mutate_resource(
                    section,
                    resource_id,
                    value,
                    expected_revision=expected(if_match),
                )
            )

        @app.delete(
            f"/api/v1/{path}/{{resource_id}}",
            name=f"delete_{section}",
            dependencies=[Depends(authorize)],
        )
        async def delete_resource(
            resource_id: str, if_match: str | None = Header(default=None)
        ) -> Response:
            return mutation(
                lambda: store.mutate_resource(
                    section,
                    resource_id,
                    None,
                    expected_revision=expected(if_match),
                )
            )

    install_resource_routes("repositories", "repositories")
    install_resource_routes("test-modules", "test_modules")
    install_resource_routes("gates", "gates")
    install_resource_routes("lab/hosts", "hosts")
    install_resource_routes("lab/devices", "devices")
    install_resource_routes("lab/setups", "setups")

    @app.post("/api/v1/gates/{gate_id}/validate", dependencies=[Depends(authorize)])
    async def validate_gate(gate_id: str) -> dict[str, Any]:
        gate = section_values("gates").get(gate_id)
        if not isinstance(gate, dict):
            raise HTTPException(status_code=404, detail="gate not found")
        lab = store.snapshot.document["lab"]
        matrix = []
        for setup_id in gate["targets"]["setups"]:
            setup = lab["setups"][setup_id]
            matrix.extend(
                {
                    "setup": setup_id,
                    "platform_key": setup.get("platform_key"),
                    "module": module_id,
                    "devices": setup["devices"],
                }
                for module_id in gate["test_modules"]
            )
        return {
            "valid": True,
            "gate_id": gate_id,
            "definition_digest": hashlib.sha256(
                json.dumps(gate, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            "matrix": matrix,
        }

    @app.post("/api/v1/gates/{gate_id}/run", dependencies=[Depends(authorize)])
    async def manual_gate(gate_id: str, request: Request) -> dict[str, Any]:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=422, detail="body must be an object")
        commit_sha = body.get("commit_sha")
        branch = body.get("branch")
        repository_id = body.get("repository_id")
        device_types = body.get("device_types")
        if commit_sha is not None and not isinstance(commit_sha, str):
            raise HTTPException(status_code=422, detail="commit_sha must be a string")
        if branch is not None and not isinstance(branch, str):
            raise HTTPException(status_code=422, detail="branch must be a string")
        if repository_id is not None and not isinstance(repository_id, str):
            raise HTTPException(status_code=422, detail="repository_id must be a string")
        if device_types is not None and (
            not isinstance(device_types, list)
            or not all(isinstance(item, str) for item in device_types)
        ):
            raise HTTPException(
                status_code=422, detail="device_types must be a list of strings"
            )
        try:
            return await asyncio.to_thread(
                engine.manual_run,
                gate_id,
                commit_sha,
                branch or None,
                repository_id=repository_id,
                device_types=device_types,
            )
        except ConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/repositories/{repository_id}/pull-requests")
    async def repository_pull_requests(repository_id: str) -> list[dict[str, Any]]:
        try:
            return await asyncio.to_thread(engine.pull_requests, repository_id)
        except ConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post(
        "/api/v1/repositories/{repository_id}/pull-requests/{number}/run",
        dependencies=[Depends(authorize)],
    )
    async def approve_pull_request(
        repository_id: str,
        number: int,
        request: Request,
    ) -> dict[str, Any]:
        body = await request.json()
        gate_id = body.get("gate_id") if isinstance(body, dict) else None
        expected_sha = body.get("expected_sha") if isinstance(body, dict) else None
        if not isinstance(gate_id, str) or not isinstance(expected_sha, str):
            raise HTTPException(
                status_code=422,
                detail="body requires gate_id and expected_sha",
            )
        gate = store.snapshot.document["gates"].get(gate_id)
        if not isinstance(gate, dict) or gate.get("repository") != repository_id:
            raise HTTPException(
                status_code=422,
                detail="gate does not belong to the selected repository",
            )
        try:
            return await asyncio.to_thread(
                engine.approve_pull_request,
                gate_id,
                number,
                expected_sha,
            )
        except ConfigError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/api/v1/events")
    async def events(limit: int = 100) -> dict[str, Any]:
        return {"events": database.list_events(limit=min(max(limit, 1), 500))}

    @app.get("/api/v1/gate-runs")
    async def gate_runs(limit: int = 100, gate_id: str | None = None) -> dict[str, Any]:
        return {
            "runs": database.list_gate_runs(
                limit=min(max(limit, 1), 500), gate_id=gate_id
            )
        }

    @app.get("/api/v1/gate-runs/{run_id}")
    async def gate_run(run_id: str) -> dict[str, Any]:
        try:
            return database.gate_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="gate run not found") from exc

    @app.get(
        "/api/v1/gate-runs/{run_id}/artifacts",
        dependencies=[Depends(authorize)],
    )
    async def gate_run_artifacts(run_id: str) -> dict[str, Any]:
        try:
            database.gate_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="gate run not found") from exc
        artifacts = database.assignment_artifacts(run_id=run_id)
        return {
            "run_id": run_id,
            "artifacts": [
                {key: value for key, value in artifact.items() if key != "storage_path"}
                for artifact in artifacts
            ],
        }

    @app.get(
        "/api/v1/gate-runs/{run_id}/artifacts/{artifact_id}",
        dependencies=[Depends(authorize)],
    )
    async def view_gate_run_artifact(run_id: str, artifact_id: str) -> dict[str, Any]:
        try:
            artifact = database.assignment_artifact(run_id, artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc
        archive_root = (_state_dir(store) / "archive").resolve()
        path = Path(artifact["storage_path"]).resolve()
        if not path.is_relative_to(archive_root):
            raise HTTPException(status_code=404, detail="artifact not found")
        if not path.is_file():
            raise HTTPException(status_code=410, detail="archived artifact is missing")
        with path.open("rb") as stream:
            encoded = stream.read(1024 * 1024 + 1)
        if b"\x00" in encoded:
            raise HTTPException(
                status_code=415,
                detail="binary artifact must be downloaded instead of viewed",
            )
        truncated = len(encoded) > 1024 * 1024
        content = encoded[: 1024 * 1024].decode("utf-8", errors="replace")
        return {
            "id": artifact["id"],
            "path": artifact["relative_path"],
            "media_type": artifact["media_type"],
            "size_bytes": artifact["size_bytes"],
            "sha256": artifact["sha256"],
            "truncated": truncated,
            "content": content,
        }

    @app.get(
        "/api/v1/gate-runs/{run_id}/artifacts/{artifact_id}/download",
        dependencies=[Depends(authorize)],
    )
    async def download_gate_run_artifact(run_id: str, artifact_id: str) -> FileResponse:
        try:
            artifact = database.assignment_artifact(run_id, artifact_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="artifact not found") from exc
        archive_root = (_state_dir(store) / "archive").resolve()
        path = Path(artifact["storage_path"]).resolve()
        if not path.is_relative_to(archive_root):
            raise HTTPException(status_code=404, detail="artifact not found")
        if not path.is_file():
            raise HTTPException(status_code=410, detail="archived artifact is missing")
        return FileResponse(
            path,
            media_type=artifact["media_type"],
            filename=Path(artifact["relative_path"]).name,
        )

    @app.post("/api/v1/gate-runs/{run_id}/cancel", dependencies=[Depends(authorize)])
    async def cancel_gate_run(run_id: str) -> dict[str, Any]:
        try:
            return database.cancel_gate_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="gate run not found") from exc

    @app.post("/api/v1/gate-runs/{run_id}/retry", dependencies=[Depends(authorize)])
    async def retry_gate_run(run_id: str) -> dict[str, Any]:
        try:
            return database.retry_gate_run(run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="gate run not found") from exc

    @app.get("/api/v1/assignments")
    async def assignments(status: str | None = None) -> dict[str, Any]:
        return {"assignments": database.assignments(status=status)}

    @app.post("/api/v1/lab/hosts/{host_id}/probe", dependencies=[Depends(authorize)])
    async def probe_host(host_id: str) -> dict[str, Any]:
        host = section_values("hosts").get(host_id)
        if not isinstance(host, dict):
            raise HTTPException(status_code=404, detail="host not found")
        command = ["python3", "--version"]
        if host.get("transport") == "ssh":
            command = ["ssh", "-o", "ForwardAgent=no", host["ssh_target"], *command]
        result = await asyncio.to_thread(
            subprocess.run,
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=15,
            check=False,
        )
        return {"ok": result.returncode == 0, "output": result.stdout[:1000]}

    @app.get("/api/v1/lab/hosts/{host_id}/usb", dependencies=[Depends(authorize)])
    async def discover_usb(host_id: str) -> dict[str, Any]:
        host = section_values("hosts").get(host_id)
        if not isinstance(host, dict):
            raise HTTPException(status_code=404, detail="host not found")
        if host.get("transport") == "ssh":
            command = [
                "ssh",
                "-o",
                "ForwardAgent=no",
                host["ssh_target"],
                "find",
                "/dev/serial/by-id",
                "-maxdepth",
                "1",
                "-type",
                "l",
                "-print",
            ]
            result = await asyncio.to_thread(
                subprocess.run,
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
            paths = result.stdout.splitlines() if result.returncode == 0 else []
            detail = result.stderr[:1000] if result.returncode else None
        else:
            directory = Path("/dev/serial/by-id")
            paths = [str(item) for item in sorted(directory.iterdir())] if directory.is_dir() else []
            detail = None
        return {"host": host_id, "paths": paths, "detail": detail}

    @app.post("/api/v1/lab/devices/{device_id}/probe", dependencies=[Depends(authorize)])
    async def probe_device(device_id: str) -> dict[str, Any]:
        device = section_values("devices").get(device_id)
        if not isinstance(device, dict):
            raise HTTPException(status_code=404, detail="device not found")
        result: dict[str, Any] = {"device": device_id, "api": None, "usb": None}
        api = device.get("addresses", {}).get("api")
        if api:
            try:
                def request_api() -> int:
                    with urlopen(UrlRequest(api, method="GET"), timeout=5) as response:
                        return response.status

                result["api"] = {"ok": True, "status": await asyncio.to_thread(request_api)}
            except Exception as exc:
                result["api"] = {"ok": False, "detail": str(exc)}
        serial_path = device.get("usb", {}).get("serial_path")
        if serial_path:
            host = section_values("hosts")[device["host"]]
            if host.get("transport") == "ssh":
                check = await asyncio.to_thread(
                    subprocess.run,
                    ["ssh", "-o", "ForwardAgent=no", host["ssh_target"], "test", "-e", serial_path],
                    timeout=10,
                    check=False,
                )
                exists = check.returncode == 0
            else:
                exists = Path(serial_path).exists()
            result["usb"] = {"ok": exists, "path": serial_path}
        return result

    @app.put("/api/v1/lab/devices/{device_id}/photo", dependencies=[Depends(authorize)])
    async def upload_photo(
        device_id: str,
        request: Request,
        if_match: str | None = Header(default=None),
    ) -> Response:
        device = section_values("devices").get(device_id)
        if not isinstance(device, dict):
            raise HTTPException(status_code=404, detail="device not found")
        content_type = request.headers.get("content-type", "").split(";", 1)[0]
        suffixes = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
        if content_type not in suffixes:
            raise HTTPException(status_code=415, detail="photo must be JPEG, PNG, or WebP")
        body = await request.body()
        if not body or len(body) > 10 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="photo must be between 1 byte and 10 MiB")
        signatures = {
            "image/jpeg": body.startswith(b"\xff\xd8\xff"),
            "image/png": body.startswith(b"\x89PNG\r\n\x1a\n"),
            "image/webp": len(body) >= 12 and body[:4] == b"RIFF" and body[8:12] == b"WEBP",
        }
        if not signatures[content_type]:
            raise HTTPException(status_code=415, detail="photo content does not match its media type")
        media = _state_dir(store) / "media" / "devices"
        media.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(body).hexdigest()[:16]
        path = media / f"{device_id}-{digest}{suffixes[content_type]}"
        path.write_bytes(body)
        updated = dict(device)
        updated["photo"] = str(path.relative_to(store.source.parent)) if path.is_relative_to(store.source.parent) else str(path)
        return mutation(
            lambda: store.mutate_resource(
                "devices", device_id, updated, expected_revision=expected(if_match)
            )
        )

    @app.post("/api/v1/lab/setups/{setup_id}/preflight", dependencies=[Depends(authorize)])
    async def preflight_setup(setup_id: str) -> dict[str, Any]:
        setup = section_values("setups").get(setup_id)
        if not isinstance(setup, dict):
            raise HTTPException(status_code=404, detail="setup not found")
        checks = []
        for role, device_id in setup["devices"].items():
            checks.append({"role": role, **(await probe_device(device_id))})
        return {
            "setup": setup_id,
            "ok": all(
                all(value is None or value.get("ok") for value in (item["api"], item["usb"]))
                for item in checks
            ),
            "devices": checks,
        }

    def ui(page: str) -> str:
        return render_page(
            page,
            store.snapshot,
            runs=database.list_gate_runs(limit=20),
        )

    @app.get("/", response_class=HTMLResponse)
    async def overview_page() -> str:
        return ui("overview")

    @app.get("/gates", response_class=HTMLResponse)
    async def gates_page() -> str:
        return ui("gates")

    @app.get("/lab", response_class=HTMLResponse)
    async def lab_page() -> str:
        return ui("lab")

    @app.get("/trigger", response_class=HTMLResponse)
    async def trigger_page() -> str:
        return ui("trigger")

    @app.get("/config", response_class=HTMLResponse)
    async def advanced_page() -> str:
        return ui("advanced")

    return app
