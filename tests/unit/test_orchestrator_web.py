from __future__ import annotations

import asyncio
import hashlib
import json
import re
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import yaml

from mining_qa_lab.config import ConfigStore
from mining_qa_lab.database import OrchestratorDatabase
from mining_qa_lab.engine import OrchestratorEngine
from mining_qa_lab.errors import ConfigError
from test_orchestrator import configuration

try:
    from httpx import ASGITransport, AsyncClient

    from mining_qa_lab.web import create_app
except ImportError:
    ASGITransport = None  # type: ignore[assignment,misc]
    AsyncClient = None  # type: ignore[assignment,misc]
    create_app = None  # type: ignore[assignment]


@unittest.skipUnless(AsyncClient is not None, "orchestrator web extra is not installed")
class OrchestratorApiTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.path = self.root / "orchestrator.yaml"
        self.path.write_text(
            yaml.safe_dump(configuration(self.root), sort_keys=False), encoding="utf-8"
        )
        self.store = ConfigStore(self.path)
        self.database = OrchestratorDatabase(self.root / "state.sqlite3")
        self.addCleanup(self.database.close)
        self.engine = OrchestratorEngine(self.store, self.database)
        with mock.patch.dict(
            "os.environ", {"MINER_ORCHESTRATOR_API_TOKEN": "local-token"}
        ):
            app = create_app(self.store, self.database, self.engine)
            self.client = AsyncClient(
                transport=ASGITransport(app=app), base_url="http://orchestrator.test"
            )
        self.addAsyncCleanup(self.client.aclose)

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": "Bearer local-token"}

    async def test_exposes_openapi_health_and_configuration_etag(self) -> None:
        health = await self.client.get("/api/v1/health")
        config = await self.client.get("/api/v1/config")
        schema = await self.client.get("/openapi.json")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(config.status_code, 200)
        self.assertEqual(config.headers["etag"], self.store.snapshot.etag)
        self.assertIn("/api/v1/gates/{resource_id}", schema.json()["paths"])
        self.assertIn("/api/v1/lab/devices/{device_id}/photo", schema.json()["paths"])
        self.assertIn(
            "/api/v1/gate-runs/{run_id}/artifacts", schema.json()["paths"]
        )
        self.assertIn(
            "/api/v1/gate-runs/{run_id}/retry", schema.json()["paths"]
        )

    async def test_resource_mutation_requires_token_and_current_etag(self) -> None:
        current = await self.client.get("/api/v1/config")
        repository = self.store.snapshot.document["repositories"]["firmware"] | {
            "polling_seconds": 120
        }
        denied = await self.client.patch(
            "/api/v1/repositories/firmware",
            headers={"If-Match": current.headers["etag"]},
            json=repository,
        )
        changed = await self.client.patch(
            "/api/v1/repositories/firmware",
            headers={**self.auth, "If-Match": current.headers["etag"]},
            json=repository,
        )
        stale = await self.client.patch(
            "/api/v1/repositories/firmware",
            headers={**self.auth, "If-Match": current.headers["etag"]},
            json=repository,
        )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(changed.status_code, 200)
        self.assertEqual(stale.status_code, 412)
        self.assertEqual(
            ConfigStore(self.path).snapshot.document["repositories"]["firmware"][
                "polling_seconds"
            ],
            120,
        )

    async def test_yaml_editor_and_photo_api_use_the_same_configuration_store(self) -> None:
        dashboard = await self.client.get("/")
        current = await self.client.get("/api/v1/config")
        photo = await self.client.put(
            "/api/v1/lab/devices/bonanza/photo",
            headers={
                **self.auth,
                "If-Match": current.headers["etag"],
                "Content-Type": "image/png",
            },
            content=b"\x89PNG\r\n\x1a\nexample",
        )

        self.assertEqual(dashboard.status_code, 200)
        self.assertNotIn("cdn.jsdelivr.net", dashboard.text)
        self.assertEqual(photo.status_code, 200)
        configured_photo = self.store.snapshot.document["lab"]["devices"]["bonanza"][
            "photo"
        ]
        self.assertTrue((self.path.parent / configured_photo).exists())

    async def test_exposes_separate_gate_lab_trigger_and_advanced_pages(self) -> None:
        pages = {
            "/": "Lab overview",
            "/gates": "Gate setup",
            "/lab": "Lab and devices",
            "/trigger": "Run gates",
            "/config": "Advanced configuration",
        }
        for path, title in pages.items():
            with self.subTest(path=path):
                response = await self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertIn(title, response.text)
                self.assertIn('href="/gates"', response.text)
                self.assertIn('href="/lab"', response.text)
                self.assertIn('href="/trigger"', response.text)
        gates = await self.client.get("/gates")
        lab = await self.client.get("/lab")
        trigger = await self.client.get("/trigger")
        self.assertIn('data-kind="gate"', gates.text)
        self.assertIn('data-kind="device"', lab.text)
        self.assertIn('class="manual-run-form"', trigger.text)
        self.assertIn("'manual_device_types'", trigger.text)
        self.assertIn('data-action="approve-pr"', trigger.text)

    async def test_overview_retries_failed_gate_through_authenticated_api(self) -> None:
        run = self.engine.manual_run("firmware-smoke", "a" * 40, "main")
        assignments = self.database.assignments(run["id"])
        failed = assignments[0]
        self.assertTrue(self.database.acquire(failed["id"], []))
        self.database.finish_assignment(
            failed["id"], status="failed", detail="pool port mismatch"
        )
        for assignment in assignments[1:]:
            self.assertTrue(self.database.acquire(assignment["id"], []))
            self.database.finish_assignment(assignment["id"], status="passed")
        self.database.update_gate_run(
            run["id"], status="failed", summary="retry regression"
        )

        dashboard = await self.client.get("/")
        bootstrap_match = re.search(
            r'<script id="bootstrap" type="application/json">(.*?)</script>',
            dashboard.text,
        )
        self.assertIsNotNone(bootstrap_match)
        bootstrap = json.loads(bootstrap_match.group(1))
        rendered_run = next(
            item for item in bootstrap["runs"] if item["id"] == run["id"]
        )
        denied = await self.client.post(f"/api/v1/gate-runs/{run['id']}/retry")
        retried = await self.client.post(
            f"/api/v1/gate-runs/{run['id']}/retry", headers=self.auth
        )

        self.assertTrue(rendered_run["retryable"])
        self.assertIn('data-action="retry-run"', dashboard.text)
        self.assertIn("Retry incomplete assignments", dashboard.text)
        self.assertEqual(denied.status_code, 401)
        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.json()["status"], "queued")
        by_id = {item["id"]: item for item in retried.json()["assignments"]}
        self.assertEqual(by_id[failed["id"]]["status"], "queued")
        self.assertEqual(by_id[failed["id"]]["attempt"], 1)
        self.assertIsNone(by_id[failed["id"]]["detail"])
        self.assertTrue(
            all(by_id[item["id"]]["status"] == "passed" for item in assignments[1:])
        )

    async def test_manual_gate_defaults_to_latest_main_or_master_and_device_types(self) -> None:
        document = self.store.snapshot.document
        updated = yaml.safe_load(yaml.safe_dump(document))
        updated["lab"]["devices"]["gamma"] = {
            "name": "Gamma",
            "type": "bitaxe_602",
            "host": "local",
            "addresses": {"api": "http://gamma.local"},
        }
        updated["lab"]["setups"]["gamma-bench"] = {
            "host": "local",
            "platform_key": "bitaxe-gamma-602",
            "runner_profile": "gamma.toml",
            "devices": {"miner": "gamma"},
        }
        updated["gates"]["firmware-smoke"]["targets"]["setups"].append(
            "gamma-bench"
        )
        for module in updated["test_modules"].values():
            module["device_types"].append("bitaxe_602")
        self.store.replace(updated, expected_revision=self.store.snapshot.revision)

        class Github:
            def branch_head(self, repository, branch):
                self.repository = repository
                if branch == "main":
                    raise ConfigError("main does not exist")
                return "b" * 40, None

        github = Github()
        self.engine.collector.github = github  # type: ignore[assignment]
        response = await self.client.post(
            "/api/v1/gates/firmware-smoke/run",
            headers=self.auth,
            json={
                "repository_id": "firmware",
                "commit_sha": None,
                "branch": None,
                "device_types": ["bitaxe_602"],
            },
        )

        self.assertEqual(response.status_code, 200)
        run = response.json()
        self.assertEqual(run["commit_sha"], "b" * 40)
        self.assertEqual(run["branch"], "master")
        self.assertEqual(github.repository, "owner/firmware")
        assignments = self.database.assignments(run["id"])
        self.assertEqual({item["setup_id"] for item in assignments}, {"gamma-bench"})
        event = self.database.list_events()[0]
        self.assertEqual(event["payload"]["device_types"], ["bitaxe_602"])
        self.assertEqual(event["payload"]["source_resolution"], "latest_project_branch")

    async def test_local_artifact_archive_requires_auth_and_supports_view_download(self) -> None:
        run = self.engine.manual_run("firmware-smoke", "a" * 40, "main")
        assignment = self.database.assignments(run["id"])[0]
        archived = self.root / "state" / "archive" / "runner.log"
        archived.parent.mkdir(parents=True)
        archived.write_text("private local runner output\n", encoding="utf-8")
        self.database.record_assignment_artifacts(
            [
                {
                    "id": "artifact-1",
                    "assignment_id": assignment["id"],
                    "attempt": 1,
                    "relative_path": "runner.log",
                    "size_bytes": archived.stat().st_size,
                    "sha256": hashlib.sha256(archived.read_bytes()).hexdigest(),
                    "media_type": "text/plain",
                    "storage_path": str(archived),
                }
            ]
        )

        denied = await self.client.get(f"/api/v1/gate-runs/{run['id']}/artifacts")
        listed = await self.client.get(
            f"/api/v1/gate-runs/{run['id']}/artifacts", headers=self.auth
        )
        viewed = await self.client.get(
            f"/api/v1/gate-runs/{run['id']}/artifacts/artifact-1",
            headers=self.auth,
        )
        downloaded = await self.client.get(
            f"/api/v1/gate-runs/{run['id']}/artifacts/artifact-1/download",
            headers=self.auth,
        )

        self.assertEqual(denied.status_code, 401)
        self.assertEqual(listed.status_code, 200)
        self.assertNotIn("storage_path", listed.json()["artifacts"][0])
        self.assertEqual(viewed.json()["content"], "private local runner output\n")
        self.assertEqual(downloaded.content, b"private local runner output\n")

    async def test_lists_and_approves_an_exact_untrusted_pull_request_head(self) -> None:
        pull = {
            "number": 73,
            "title": "Exercise candidate firmware",
            "html_url": "https://github.example/owner/firmware/pull/73",
            "state": "open",
            "draft": False,
            "updated_at": "2026-08-08T12:00:00Z",
            "user": {"login": "mallory"},
            "head": {"sha": "b" * 40, "ref": "candidate"},
            "base": {"sha": "a" * 40, "ref": "main"},
        }

        class Github:
            def open_pull_requests(self, repository):
                return [pull]

            def pull_request(self, repository, number):
                self.repository = repository
                self.number = number
                return pull

            def changed_paths(self, repository, base, head):
                return ["doc/explicit-approval-bypasses-path-filter.md"]

        github = Github()
        self.engine.collector.github = github  # type: ignore[assignment]
        listed = await self.client.get(
            "/api/v1/repositories/firmware/pull-requests"
        )
        approved = await self.client.post(
            "/api/v1/repositories/firmware/pull-requests/73/run",
            headers=self.auth,
            json={"gate_id": "firmware-smoke", "expected_sha": "b" * 40},
        )
        stale = await self.client.post(
            "/api/v1/repositories/firmware/pull-requests/73/run",
            headers=self.auth,
            json={"gate_id": "firmware-smoke", "expected_sha": "c" * 40},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["contributor"], "mallory")
        self.assertFalse(listed.json()[0]["trusted"])
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.json()["pr_number"], 73)
        self.assertEqual(approved.json()["trigger_type"], "pull_request")
        self.assertEqual(stale.status_code, 422)
        self.assertIn("head changed", stale.json()["detail"])
        event = self.database.list_events()[0]
        self.assertTrue(event["payload"]["approved"])
        self.assertEqual(event["payload"]["gate_id"], "firmware-smoke")
        self.assertEqual(github.repository, "owner/firmware")
        self.assertEqual(github.number, 73)

    async def test_no_auth_mode_allows_only_configured_client_networks(self) -> None:
        path = self.root / "open-orchestrator.yaml"
        document = configuration(self.root)
        document["controller"]["auth_mode"] = "none"
        document["controller"]["allowed_networks"] = [
            "127.0.0.0/8",
            "192.168.1.0/24",
        ]
        path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        store = ConfigStore(path)
        database = OrchestratorDatabase(self.root / "open-state.sqlite3")
        self.addCleanup(database.close)
        app = create_app(store, database)

        async with AsyncClient(
            transport=ASGITransport(app=app, client=("192.168.1.25", 12345)),
            base_url="http://orchestrator.test",
        ) as allowed:
            current = await allowed.get("/api/v1/config")
            repository = store.snapshot.document["repositories"]["firmware"] | {
                "polling_seconds": 120
            }
            changed = await allowed.patch(
                "/api/v1/repositories/firmware",
                headers={"If-Match": current.headers["etag"]},
                json=repository,
            )
            dashboard = await allowed.get("/")

        async with AsyncClient(
            transport=ASGITransport(app=app, client=("203.0.113.25", 12345)),
            base_url="http://orchestrator.test",
        ) as denied:
            blocked = await denied.get("/api/v1/health")

        self.assertEqual(changed.status_code, 200)
        self.assertNotIn("Paste the local API token", dashboard.text)
        self.assertEqual(blocked.status_code, 403)

    async def test_central_service_runs_one_persistent_agent_and_operator_controls(self) -> None:
        path = self.root / "central-orchestrator.yaml"
        document = {
            "schema_version": 1,
            "controller": {
                "state_dir": str(self.root / "central-state"),
                "auth_mode": "bearer",
            },
            "coordination": {
                "mode": "central",
                "central": {
                    "base_url": "http://127.0.0.1:3000",
                    "lab_id": "lab-east",
                    "token_env": "MINING_QA_TOKEN",
                    "subscriptions": {"gates": ["firmware-advisory"]},
                },
            },
            "bindings": {
                "suite_requirements": {
                    "gamma-http-and-stratum": {
                        "execution": "mock",
                        "profile": str(self.root / "mock-profile.toml"),
                        "testcode_root": str(self.root / "testcode"),
                        "mock_base_url_env": "MINING_QA_MOCK_URL",
                        "platform_class": "gamma-600",
                        "device_model": "Gamma 602",
                        "capabilities": ["http", "stratum-v1"],
                        "resources": ["mock:gamma-602"],
                        "testcode_commit": "a" * 40,
                    }
                }
            },
        }
        path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        store = ConfigStore(path)
        database = OrchestratorDatabase(self.root / "central.sqlite3")
        self.addCleanup(database.close)
        started = threading.Event()
        observed_stops: list[threading.Event] = []

        def persistent_agent(_store, _database, *, stop, **_kwargs):
            observed_stops.append(stop)
            started.set()
            stop.wait(2)
            return 1

        with (
            mock.patch.dict(
                "os.environ",
                {
                    "MINER_ORCHESTRATOR_API_TOKEN": "central-local-token",
                    "MINING_QA_TOKEN": "mqa_" + "a" * 43,
                },
            ),
            mock.patch(
                "mining_qa_lab.central.run_central_forever",
                side_effect=persistent_agent,
            ) as run_agent,
        ):
            app = create_app(store, database)
            lifespan = app.router.lifespan_context(app)
            await asyncio.wait_for(lifespan.__aenter__(), timeout=2)
            try:
                for _ in range(100):
                    if started.is_set():
                        break
                    await asyncio.sleep(0.01)
                self.assertTrue(started.is_set())
                async with AsyncClient(
                    transport=ASGITransport(app=app),
                    base_url="http://orchestrator.test",
                ) as client:
                    dashboard = await client.get("/")
                    paused = await client.post(
                        "/api/v1/central/pause",
                        headers={"Authorization": "Bearer central-local-token"},
                    )
                    resumed = await client.post(
                        "/api/v1/central/resume",
                        headers={"Authorization": "Bearer central-local-token"},
                    )
            finally:
                await asyncio.wait_for(
                    lifespan.__aexit__(None, None, None), timeout=3
                )

            run_agent.assert_called_once()
            self.assertTrue(observed_stops[0].is_set())
            self.assertEqual(paused.status_code, 200)
            self.assertTrue(paused.json()["paused"])
            self.assertEqual(resumed.status_code, 200)
            self.assertFalse(resumed.json()["paused"])
            self.assertIn("Central coordination agent", dashboard.text)
            self.assertIn("Manual trigger ownership is centralized", dashboard.text)


if __name__ == "__main__":
    unittest.main()
