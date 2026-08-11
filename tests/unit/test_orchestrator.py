from __future__ import annotations

import json
import re
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import yaml

from mining_qa_lab.errors import ConfigError
from mining_qa_lab.config import ConfigStore, validate_config
from mining_qa_lab.database import OrchestratorDatabase
from mining_qa_lab.engine import (
    MAX_RESULT_POINTER_BYTES,
    OrchestratorEngine,
    Planner,
    _load_result_pointer,
)
from mining_qa_lab.events import EventCollector, cron_matches, paths_match
from mining_qa_lab.http import PublishError
from mining_qa_lab.qa_status import GatePublisher
from mining_qa_lab.reruns import QaStatusRerunError, _claim
from mining_qa_lab.testcode import TestcodeInstallation
from mining_qa_lab.ui import render_page


def configuration(root: Path) -> dict:
    return {
        "schema_version": 1,
        "controller": {"state_dir": str(root / "state")},
        "qa_status": {"enabled": False},
        "repositories": {
            "firmware": {
                "repository": "owner/firmware",
                "pushes": {"branches": ["main", "master"]},
                "pull_requests": {
                    "base_branches": ["main", "master"],
                    "trusted_contributors": ["alice"],
                },
            }
        },
        "test_modules": {
            "smoke": {
                "pattern": "test_smoke.py",
                "device_types": ["bitaxe_bonanza"],
                "required_interfaces": ["api"],
            },
            "regression": {
                "pattern": "test_regression.py",
                "device_types": ["bitaxe_bonanza"],
            },
        },
        "lab": {
            "hosts": {"local": {"transport": "local"}},
            "devices": {
                "bonanza": {
                    "name": "Bonanza",
                    "type": "bitaxe_bonanza",
                    "host": "local",
                    "addresses": {"api": "http://bitaxe.local"},
                    "usb": {"serial_path": "/dev/serial/by-id/example"},
                    "tags": ["bonanza"],
                }
            },
            "setups": {
                "bench": {
                    "host": "local",
                    "platform_key": "bitaxe-bonanza-1002",
                    "runner_profile": "runner.toml",
                    "devices": {"miner": "bonanza"},
                }
            },
        },
        "gates": {
            "firmware-smoke": {
                "repository": "firmware",
                "triggers": {"pushes": True, "pull_requests": True, "schedules": []},
                "changes": {"include": ["src/**"], "exclude": ["doc/**"]},
                "test_modules": ["smoke", "regression"],
                "targets": {"setups": ["bench"]},
                "required": "all",
            }
        },
    }


class ConfigStoreTest(unittest.TestCase):
    def test_validates_references_and_writes_revision_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(configuration(root), sort_keys=False))
            store = ConfigStore(path)
            original = store.snapshot
            updated = configuration(root)
            updated["gates"]["firmware-smoke"]["name"] = "Firmware qualification"
            replacement = store.replace(updated, expected_revision=original.revision)

            self.assertNotEqual(original.revision, replacement.revision)
            self.assertEqual(ConfigStore(path).snapshot.revision, replacement.revision)
            self.assertEqual(len(list((root / ".orchestrator-backups").glob("*.bak"))), 1)
            with self.assertRaisesRegex(ConfigError, "revision"):
                store.replace(updated, expected_revision=original.revision)

    def test_rejects_plaintext_secrets_and_broken_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = configuration(Path(directory))
            document["qa_status"]["token"] = "secret"
            with self.assertRaisesRegex(ConfigError, "plaintext secrets"):
                validate_config(document)

            document = configuration(Path(directory))
            document["gates"]["firmware-smoke"]["targets"]["setups"] = ["missing"]
            with self.assertRaisesRegex(ConfigError, "unknown setup"):
                validate_config(document)

    def test_no_auth_requires_valid_allowed_networks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = configuration(Path(directory))
            document["controller"]["auth_mode"] = "none"
            with self.assertRaisesRegex(ConfigError, "allowed_networks must not be empty"):
                validate_config(document)

            document["controller"]["allowed_networks"] = ["not-a-network"]
            with self.assertRaisesRegex(ConfigError, "IPv4 or IPv6 network"):
                validate_config(document)

            document["controller"]["allowed_networks"] = [
                "127.0.0.0/8",
                "192.168.1.0/24",
            ]
            normalized = validate_config(document)
            self.assertEqual(normalized["controller"]["auth_mode"], "none")

    def test_qa_status_event_source_requires_enabled_qa_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = configuration(Path(directory))
            document["repositories"]["firmware"]["event_source"] = "qa_status"
            with self.assertRaisesRegex(ConfigError, "requires qa_status.enabled"):
                validate_config(document)

            document["qa_status"]["enabled"] = True
            document["qa_status"]["base_url"] = "https://qa.example"
            normalized = validate_config(document)
            self.assertEqual(
                normalized["repositories"]["firmware"]["event_source"],
                "qa_status",
            )

    def test_qa_status_rerun_polling_is_explicitly_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = configuration(Path(directory))
            normalized = validate_config(document)
            self.assertFalse(normalized["qa_status"]["reruns_enabled"])

            document["qa_status"] = {
                "enabled": True,
                "reruns_enabled": True,
                "base_url": "https://qa.example",
                "token_env": "TEST_QA_TOKEN",
            }
            self.assertTrue(validate_config(document)["qa_status"]["reruns_enabled"])

            document["qa_status"]["reruns_enabled"] = "yes"
            with self.assertRaisesRegex(ConfigError, "reruns_enabled must be boolean"):
                validate_config(document)

    def test_validates_artifact_deployment_and_module_profile_override(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            document = configuration(Path(directory))
            document["repositories"]["firmware"]["artifacts"] = {
                "ota": {
                    "workflow": "build.yml",
                    "artifact_name": "esp-miner.bin",
                    "filename": "esp-miner.bin",
                }
            }
            document["test_modules"]["regression"]["runner_profile"] = (
                "regression.toml"
            )
            document["lab"]["devices"]["bonanza"]["expected"] = {
                "board_version": "1002"
            }
            document["gates"]["firmware-smoke"]["deployment"] = {
                "artifact": "ota",
                "device_roles": ["miner"],
            }
            validated = validate_config(document)

            self.assertEqual(
                validated["test_modules"]["regression"]["runner_profile"],
                "regression.toml",
            )
            self.assertEqual(
                validated["gates"]["firmware-smoke"]["deployment"]["method"],
                "esp_miner_http_ota",
            )

    def test_validates_opt_in_testcode_installation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = configuration(root)
            document["testcode"] = {
                "enabled": True,
                "repository": "johnny9/mining-qa-testcode",
                "ref": "main",
                "install_timeout": 120,
            }
            document["lab"]["hosts"]["local"]["testcode"] = {
                "checkout": str(root / "testcode"),
                "venv": str(root / "runner-venv"),
            }
            validated = validate_config(document)
            self.assertTrue(validated["testcode"]["enabled"])
            self.assertEqual(
                validated["lab"]["hosts"]["local"]["testcode"]["python"],
                "python3",
            )

            invalid = configuration(root)
            invalid["testcode"] = {"enabled": True, "ref": "../main"}
            with self.assertRaisesRegex(ConfigError, "safe Git branch"):
                validate_config(invalid)

            invalid = configuration(root)
            invalid["testcode"] = {"enabled": True}
            with self.assertRaisesRegex(ConfigError, "testcode is required"):
                validate_config(invalid)

            invalid = configuration(root)
            invalid["testcode"] = {"enabled": True}
            invalid["lab"]["hosts"]["local"]["testcode"] = {
                "checkout": "relative/source",
                "venv": str(root / "runner-venv"),
            }
            with self.assertRaisesRegex(ConfigError, "absolute non-root"):
                validate_config(invalid)

            invalid = configuration(root)
            invalid["testcode"] = {"enabled": True}
            invalid["lab"]["hosts"]["local"]["testcode"] = {
                "checkout": str(root / "source"),
                "venv": str(root / "source" / ".venv"),
            }
            with self.assertRaisesRegex(ConfigError, "must not overlap"):
                validate_config(invalid)


class RemoteRerunTest(unittest.TestCase):
    @staticmethod
    def terminal_run(root: Path) -> tuple[OrchestratorDatabase, dict, list[dict]]:
        config = validate_config(configuration(root))
        database = OrchestratorDatabase(root / "state.sqlite3")
        event, _ = database.create_event(
            event_key="manual:rerun-source",
            repository_id="firmware",
            trigger_type="manual",
            commit_sha="a" * 40,
            branch="main",
        )
        run, _ = database.create_gate_run(
            gate_id="firmware-smoke",
            event=event,
            definition_digest="b" * 64,
            required_policy="all",
            assignments=[
                {
                    "setup_id": "bench",
                    "module_id": "smoke",
                    "platform_key": "bitaxe-bonanza-1002",
                },
                {
                    "setup_id": "bench",
                    "module_id": "regression",
                    "platform_key": "bitaxe-bonanza-1002",
                },
            ],
            config_snapshot=config,
        )
        assignments = database.assignments(run["id"])
        database.acquire(assignments[0]["id"], [])
        database.acquire(assignments[1]["id"], [])
        database.finish_assignment(assignments[0]["id"], status="passed")
        database.finish_assignment(assignments[1]["id"], status="failed")
        database.update_gate_run(
            run["id"],
            status="failed",
            qa_result_id="12f10026-a596-4567-860f-f238ff394912",
        )
        return database, database.gate_run(run["id"]), assignments

    @staticmethod
    def request(run: dict, *, request_id: str, mode: str, assignment_ids: list[str]) -> dict:
        return {
            "id": request_id,
            "claim_token": "457eb7df-a3f8-42fb-b9dd-01cfebbc4815",
            "gate_run_id": run["qa_result_id"],
            "external_run_id": run["id"],
            "repository": "owner/firmware",
            "gate_key": "firmware-smoke",
            "commit_sha": "a" * 40,
            "mode": mode,
            "assignment_ids": assignment_ids,
        }

    def test_selected_remote_rerun_is_atomic_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, run, assignments = self.terminal_run(Path(directory))
            request = self.request(
                run,
                request_id="c21fd938-04ed-4e28-9f16-24ec933931c4",
                mode="assignments",
                assignment_ids=[assignments[0]["id"]],
            )

            first = database.apply_remote_rerun(request)
            self.assertTrue(first["applied"])
            updated = database.gate_run(run["id"])
            self.assertEqual(updated["status"], "queued")
            self.assertEqual(updated["assignments"][0]["status"], "queued")
            self.assertEqual(updated["assignments"][1]["status"], "failed")
            self.assertEqual(updated["assignments"][0]["attempt"], 1)

            self.assertTrue(database.acquire(assignments[0]["id"], []))
            second = database.apply_remote_rerun(request)
            self.assertFalse(second["applied"])
            self.assertEqual(
                database.gate_run(run["id"])["assignments"][0]["status"],
                "running",
            )
            with self.assertRaisesRegex(ValueError, "assignments changed"):
                database.apply_remote_rerun(
                    {**request, "assignment_ids": [assignments[1]["id"]]}
                )
            database.close()

    def test_whole_gate_remote_rerun_requeues_every_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, run, assignments = self.terminal_run(Path(directory))
            result = database.apply_remote_rerun(
                self.request(
                    run,
                    request_id="26407f75-c2f6-4f2f-856f-b7ad31f02c97",
                    mode="all",
                    assignment_ids=[],
                )
            )

            self.assertTrue(result["applied"])
            rerun = database.gate_run(run["id"])
            self.assertEqual(
                [item["status"] for item in rerun["assignments"]],
                ["queued", "queued"],
            )
            self.assertEqual([item["attempt"] for item in rerun["assignments"]], [1, 1])
            database.close()

    def test_claim_response_validation_is_bounded_and_typed(self) -> None:
        request = _claim(
            {
                "request": {
                    "id": "26407f75-c2f6-4f2f-856f-b7ad31f02c97",
                    "claim_token": "457eb7df-a3f8-42fb-b9dd-01cfebbc4815",
                    "gate_run_id": "12f10026-a596-4567-860f-f238ff394912",
                    "external_run_id": "local-run",
                    "repository": "owner/firmware",
                    "gate_key": "firmware-smoke",
                    "commit_sha": "a" * 40,
                    "mode": "assignments",
                    "assignment_ids": ["assignment-1", "assignment-1"],
                }
            }
        )
        self.assertEqual(request["assignment_ids"], ["assignment-1"])
        with self.assertRaisesRegex(QaStatusRerunError, "invalid assignments"):
            _claim({"request": {**request, "assignment_ids": ["x"] * 101}})

    def test_remote_rerun_rejects_mismatch_and_active_target(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database, run, assignments = self.terminal_run(Path(directory))
            mismatched = self.request(
                run,
                request_id="970c59f6-fc6e-4e52-81ce-8c8ecac51c07",
                mode="all",
                assignment_ids=[],
            )
            mismatched["commit_sha"] = "c" * 40
            with self.assertRaisesRegex(ValueError, "commit"):
                database.apply_remote_rerun(mismatched)

            database.retry_gate_run(run["id"])
            with self.assertRaisesRegex(ValueError, "active"):
                database.apply_remote_rerun(
                    self.request(
                        run,
                        request_id="c7e3cb55-d728-4846-a5ad-acd2cb33305b",
                        mode="all",
                        assignment_ids=[],
                    )
                )
            self.assertEqual(
                {item["status"] for item in database.assignments(run["id"])},
                {"passed", "queued"},
            )
            database.close()

    def test_engine_claims_only_configured_targets_and_resolves_acceptance(self) -> None:
        class Client:
            def __init__(self, request: dict) -> None:
                self.request = request
                self.resolutions: list[tuple] = []

            def claim(self, config, targets):
                self.assert_targets(targets)
                value, self.request = self.request, None
                return value

            @staticmethod
            def assert_targets(targets):
                if targets != [
                    {"repository": "owner/firmware", "gate_key": "firmware-smoke"}
                ]:
                    raise AssertionError(targets)

            def resolve(self, config, request_id, claim_token, outcome, detail=None):
                self.resolutions.append(
                    (request_id, claim_token, outcome, detail)
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database, run, assignments = self.terminal_run(root)
            document = configuration(root)
            document["qa_status"] = {
                "enabled": True,
                "reruns_enabled": True,
                "base_url": "https://qa.example",
                "token_env": "TEST_QA_TOKEN",
            }
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            engine = OrchestratorEngine(ConfigStore(path), database)
            client = Client(
                self.request(
                    run,
                    request_id="878ee57b-6089-4a35-bf25-6beb211840a8",
                    mode="assignments",
                    assignment_ids=[assignments[1]["id"]],
                )
            )
            engine.rerun_client = client  # type: ignore[assignment]

            self.assertEqual(engine.poll_reruns(), 1)
            self.assertEqual(client.resolutions[0][2], "accepted")
            self.assertEqual(database.assignments(run["id"])[1]["status"], "queued")
            database.close()


class SchedulingTest(unittest.TestCase):
    def test_result_pointer_contract_is_bounded_and_versioned(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pointer = Path(directory) / "result-pointer.json"
            pointer.write_text(
                json.dumps(
                    {
                        "contract_version": 1,
                        "status": "passed",
                        "publishers": [],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(_load_result_pointer(pointer)["contract_version"], 1)

            pointer.write_text(
                json.dumps({"contract_version": 2, "publishers": []}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(PublishError, "unsupported.*version"):
                _load_result_pointer(pointer)

            pointer.write_bytes(b" " * (MAX_RESULT_POINTER_BYTES + 1))
            with self.assertRaisesRegex(PublishError, "exceeds"):
                _load_result_pointer(pointer)

            pointer.unlink()
            with self.assertRaisesRegex(PublishError, "did not write"):
                _load_result_pointer(pointer)

    def test_cron_and_change_filters(self) -> None:
        when = datetime(2026, 8, 8, 3, 17, tzinfo=UTC)
        self.assertTrue(cron_matches("17 3 * * *", when))
        self.assertTrue(cron_matches("*/17 3 * * 6", when))
        self.assertFalse(cron_matches("18 3 * * *", when))
        self.assertTrue(paths_match(["src/main.c"], {"include": ["src/**"]}))
        self.assertFalse(
            paths_match(
                ["doc/design.md"],
                {"include": ["**"], "exclude": ["doc/**"]},
            )
        )

    def test_push_event_carries_merged_pull_request_metadata(self) -> None:
        class Github:
            def branch_head(self, repository, branch):
                return "b" * 40, None

            def changed_paths(self, repository, base, head):
                return ["src/main.c"]

            def merged_pull_request(self, repository, commit_sha, base_branch):
                return {
                    "number": 42,
                    "html_url": "https://github.example/pull/42",
                    "merged_at": "2026-08-08T00:00:00Z",
                    "user": {"login": "alice"},
                    "base": {"ref": "main"},
                }

            def open_pull_requests(self, repository):
                return []

        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "state.sqlite3")
            database.set_cursor(
                "github:owner/firmware:branch:main",
                "a" * 40,
            )
            collector = EventCollector(database, Github())  # type: ignore[arg-type]
            created = collector.poll_repository(
                "firmware",
                {
                    "repository": "owner/firmware",
                    "pushes": {"branches": ["main"]},
                    "pull_requests": {
                        "base_branches": ["main"],
                        "trusted_contributors": ["alice"],
                    },
                },
            )
            event = database.list_events()[0]
            database.close()

        self.assertEqual(created, 1)
        self.assertEqual(event["trigger_type"], "push")
        self.assertEqual(event["pr_number"], 42)
        self.assertEqual(event["contributor"], "alice")

    def test_qa_status_feed_uses_independent_local_cursors(self) -> None:
        class Feed:
            def __init__(self) -> None:
                self.baselines = 0
                self.polls = 0

            def deliveries(self, config, repository, *, after, latest):
                if latest:
                    self.baselines += 1
                    return {"deliveries": [], "next_cursor": "baseline-id"}
                self.assert_after(after)
                self.polls += 1
                return {
                    "deliveries": [
                        {
                            "id": "delivery-cursor-id",
                            "delivery_id": "github-delivery-id",
                            "event_type": "push",
                            "repository": "owner/firmware",
                            "ref": "refs/heads/main",
                            "commit_sha": "c" * 40,
                            "sender_login": "alice",
                            "changed_paths": ["src/main.c"],
                        }
                    ],
                    "next_cursor": "delivery-cursor-id",
                }

            @staticmethod
            def assert_after(after):
                if after != "baseline-id":
                    raise AssertionError(after)

        with tempfile.TemporaryDirectory() as directory:
            feed = Feed()
            repository = {
                "repository": "owner/firmware",
                "event_source": "qa_status",
                "pushes": {"branches": ["main"]},
                "pull_requests": {
                    "base_branches": ["main"],
                    "trusted_contributors": ["alice"],
                },
            }
            qa_status = {
                "enabled": True,
                "base_url": "https://qa.example",
                "token_env": "TEST_QA_TOKEN",
            }

            events = []
            cursors = []
            for name in ("primary", "redundant"):
                database = OrchestratorDatabase(Path(directory) / f"{name}.sqlite3")
                collector = EventCollector(database, qa_status=feed)  # type: ignore[arg-type]
                self.assertEqual(
                    collector.poll_repository("firmware", repository, qa_status), 0
                )
                self.assertEqual(
                    collector.poll_repository("firmware", repository, qa_status), 1
                )
                events.append(database.list_events()[0])
                cursors.append(
                    database.cursor("qa-status:https://qa.example:owner/firmware")
                )
                database.close()

        self.assertEqual(feed.baselines, 2)
        self.assertEqual(feed.polls, 2)
        self.assertEqual([event["trigger_type"] for event in events], ["push", "push"])
        self.assertEqual([event["commit_sha"] for event in events], ["c" * 40] * 2)
        self.assertEqual(
            [cursor["value"] for cursor in cursors],
            ["delivery-cursor-id", "delivery-cursor-id"],
        )

    def test_qa_status_feed_filters_untrusted_pull_request_authors(self) -> None:
        class Feed:
            def deliveries(self, config, repository, *, after, latest):
                return {
                    "deliveries": [
                        {
                            "id": "delivery-cursor-id",
                            "delivery_id": "github-delivery-id",
                            "event_type": "pull_request",
                            "action": "synchronize",
                            "repository": "owner/firmware",
                            "commit_sha": "d" * 40,
                            "pr_number": 9,
                            "pr_head_ref": "feature",
                            "pr_base_ref": "main",
                            "pr_author_login": "mallory",
                            "changed_paths": [],
                        }
                    ],
                    "next_cursor": "delivery-cursor-id",
                }

        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "state.sqlite3")
            database.set_cursor(
                "qa-status:https://qa.example:owner/firmware", "0"
            )
            collector = EventCollector(database, qa_status=Feed())  # type: ignore[arg-type]
            created = collector.poll_repository(
                "firmware",
                {
                    "repository": "owner/firmware",
                    "event_source": "qa_status",
                    "pushes": {"branches": ["main"]},
                    "pull_requests": {
                        "base_branches": ["main"],
                        "trusted_contributors": ["alice"],
                    },
                },
                {"enabled": True, "base_url": "https://qa.example"},
            )
            events = database.list_events()
            database.close()

        self.assertEqual(created, 0)
        self.assertEqual(events, [])

    def test_plans_one_assignment_per_setup_and_module_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = validate_config(configuration(root))
            database = OrchestratorDatabase(root / "state.sqlite3")
            event, _ = database.create_event(
                event_key="push:1",
                repository_id="firmware",
                trigger_type="push",
                commit_sha="a" * 40,
                branch="main",
                changed_paths=["src/main.c"],
            )
            planner = Planner(database)
            self.assertEqual(planner.plan(config), 1)
            self.assertEqual(planner.plan(config), 0)
            runs = database.list_gate_runs()
            assignments = database.assignments(runs[0]["id"])
            database.close()

        self.assertEqual(len(assignments), 2)
        self.assertEqual({item["module_id"] for item in assignments}, {"smoke", "regression"})
        self.assertEqual({item["platform_key"] for item in assignments}, {"bitaxe-bonanza-1002"})

    def test_manual_gate_resolves_master_fallback_and_filters_device_types(self) -> None:
        class Github:
            def branch_head(self, repository, branch):
                if branch == "main":
                    raise ConfigError("main does not exist")
                return "b" * 40, None

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = configuration(root)
            document["lab"]["devices"]["gamma"] = {
                "name": "Gamma",
                "type": "bitaxe_602",
                "host": "local",
                "addresses": {"api": "http://gamma.local"},
            }
            document["lab"]["setups"]["gamma-bench"] = {
                "host": "local",
                "platform_key": "bitaxe-gamma-602",
                "runner_profile": "gamma.toml",
                "devices": {"miner": "gamma"},
            }
            document["gates"]["firmware-smoke"]["targets"]["setups"].append(
                "gamma-bench"
            )
            for module in document["test_modules"].values():
                module["device_types"].append("bitaxe_602")
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            store = ConfigStore(path)
            database = OrchestratorDatabase(root / "state.sqlite3")
            engine = OrchestratorEngine(store, database)
            engine.collector.github = Github()  # type: ignore[assignment]

            run = engine.manual_run(
                "firmware-smoke",
                repository_id="firmware",
                device_types=["bitaxe_602"],
            )
            assignments = database.assignments(run["id"])
            event = database.list_events()[0]
            database.close()

        self.assertEqual(run["commit_sha"], "b" * 40)
        self.assertEqual(run["branch"], "master")
        self.assertEqual({item["setup_id"] for item in assignments}, {"gamma-bench"})
        self.assertEqual(event["payload"]["device_types"], ["bitaxe_602"])
        self.assertEqual(event["payload"]["source_resolution"], "latest_project_branch")

    def test_executes_manual_gate_and_reads_existing_child_result_pointer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake-miner-test"
            script.write_text(
                """#!/usr/bin/env python3
import hashlib, json, os
from pathlib import Path
metadata = json.loads(os.environ["MINER_TEST_ORCHESTRATION_METADATA"])
assert metadata["contract_version"] == 1
assert metadata["gate_id"] == "firmware-smoke"
pointer = Path(os.environ["MINER_TEST_RESULT_POINTER"])
pointer.parent.mkdir(parents=True, exist_ok=True)
artifact_root = pointer.parent / "runner-artifacts"
artifact_root.mkdir()
artifact = b"sanitized child log\\n"
(artifact_root / "runner.log").write_bytes(artifact)
manifest = json.dumps({
    "version": 1,
    "run_id": "runner-run",
    "artifacts": [{
        "path": "runner.log",
        "size_bytes": len(artifact),
        "sha256": hashlib.sha256(artifact).hexdigest(),
        "media_type": "text/plain",
    }],
}, sort_keys=True).encode()
(artifact_root / "orchestration-artifacts.json").write_bytes(manifest)
pointer.write_text(json.dumps({
    "contract_version": 1,
    "status": "passed",
    "artifact_root": str(artifact_root),
    "artifact_manifest": {
        "path": "orchestration-artifacts.json",
        "size_bytes": len(manifest),
        "sha256": hashlib.sha256(manifest).hexdigest(),
    },
    "publishers": [{
        "name": "mining_qa_status", "success": True, "required": True,
        "url": "https://qa.example/results/child-result-id"
    }]
}))
""",
                encoding="utf-8",
            )
            script.chmod(0o700)
            document = configuration(root)
            document["lab"]["hosts"]["local"]["miner_test"] = str(script)
            (root / "runner.toml").write_text("", encoding="utf-8")
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            store = ConfigStore(path)
            database = OrchestratorDatabase(root / "state.sqlite3")
            engine = OrchestratorEngine(store, database)
            run = engine.manual_run("firmware-smoke", "a" * 40, "main")
            while engine.tick():
                pass
            completed = database.gate_run(run["id"])

            self.assertEqual(completed["status"], "passed")
            self.assertEqual(
                {item["qa_result_id"] for item in completed["assignments"]},
                {"child-result-id"},
            )
            self.assertTrue(
                all(Path(item["result_pointer"]).is_file() for item in completed["assignments"])
            )
            archived = database.assignment_artifacts(run_id=run["id"])
            self.assertEqual(len(archived), 2)
            self.assertTrue(
                all(
                    Path(item["storage_path"]).read_text(encoding="utf-8")
                    == "sanitized child log\n"
                    for item in archived
                )
            )
            database.close()

    def test_executes_installed_testcode_with_exact_metadata(self) -> None:
        class Installer:
            def __init__(self, installation):
                self.installation = installation
                self.calls = 0

            def ensure(self, *args):
                self.calls += 1
                return self.installation

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = root / "managed-testcode"
            checkout.mkdir()
            venv = root / "runner-venv"
            executable = venv / "bin" / "miner-test"
            executable.parent.mkdir(parents=True)
            executable.write_text(
                """#!/usr/bin/env python3
import json, os
from pathlib import Path
metadata = json.loads(os.environ["MINER_TEST_ORCHESTRATION_METADATA"])
assert metadata["testcode"] == {
    "repository": "johnny9/mining-qa-testcode",
    "ref": "main",
    "commit_sha": "c" * 40,
}
pointer = Path(os.environ["MINER_TEST_RESULT_POINTER"])
pointer.parent.mkdir(parents=True, exist_ok=True)
pointer.write_text(json.dumps({
    "contract_version": 1, "status": "passed", "publishers": []
}))
""",
                encoding="utf-8",
            )
            executable.chmod(0o700)
            (checkout / "runner.toml").write_text("", encoding="utf-8")
            installation = TestcodeInstallation(
                repository="johnny9/mining-qa-testcode",
                ref="main",
                commit_sha="c" * 40,
                checkout=checkout,
                venv=venv,
                executable=executable,
                log="testcode installed\n",
            )
            installer = Installer(installation)
            document = configuration(root)
            document["testcode"] = {"enabled": True}
            document["lab"]["hosts"]["local"]["testcode"] = {
                "checkout": str(checkout),
                "venv": str(venv),
            }
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            store = ConfigStore(path)
            database = OrchestratorDatabase(root / "state.sqlite3")
            engine = OrchestratorEngine(store, database)
            engine.executor.testcode_installer = installer  # type: ignore[assignment]
            run = engine.manual_run("firmware-smoke", "a" * 40, "main")
            while engine.tick():
                pass
            completed = database.gate_run(run["id"])
            log = Path(completed["assignments"][0]["result_pointer"]).with_name(
                "worker.log"
            )

            self.assertEqual(completed["status"], "passed")
            self.assertEqual(installer.calls, 2)
            self.assertIn("testcode installed", log.read_text(encoding="utf-8"))
            database.close()

    def test_enabled_qa_requires_published_child_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "fake-miner-test"
            script.write_text(
                """#!/usr/bin/env python3
import json, os
from pathlib import Path
pointer = Path(os.environ["MINER_TEST_RESULT_POINTER"])
pointer.parent.mkdir(parents=True, exist_ok=True)
pointer.write_text(json.dumps({
    "contract_version": 1,
    "status": "passed",
    "publishers": [],
}))
""",
                encoding="utf-8",
            )
            script.chmod(0o700)
            document = configuration(root)
            document["qa_status"] = {
                "enabled": True,
                "base_url": "https://qa.example",
                "token_env": "MINING_QA_TOKEN",
            }
            document["lab"]["hosts"]["local"]["miner_test"] = str(script)
            (root / "runner.toml").write_text("", encoding="utf-8")
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            store = ConfigStore(path)
            database = OrchestratorDatabase(root / "state.sqlite3")
            engine = OrchestratorEngine(store, database)
            run = engine.manual_run("firmware-smoke", "a" * 40, "main")
            assignment = database.assignments(run["id"])[0]

            engine.executor.execute(assignment)
            completed = database.gate_run(run["id"])

            self.assertEqual(completed["assignments"][0]["status"], "error")
            self.assertIn(
                "Mining QA Status child publication was missing",
                completed["assignments"][0]["detail"],
            )
            database.close()

    def test_testcode_install_failure_prevents_firmware_and_runner(self) -> None:
        class FailingInstaller:
            def ensure(self, *args):
                raise ConfigError("testcode install failed")

        class ForbiddenDeployer:
            def ensure(self, *args):
                raise AssertionError("firmware deploy must not run")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = configuration(root)
            document["testcode"] = {"enabled": True}
            document["lab"]["hosts"]["local"]["testcode"] = {
                "checkout": str(root / "managed-testcode"),
                "venv": str(root / "runner-venv"),
            }
            path = root / "orchestrator.yaml"
            path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
            store = ConfigStore(path)
            database = OrchestratorDatabase(root / "state.sqlite3")
            engine = OrchestratorEngine(store, database)
            engine.executor.testcode_installer = FailingInstaller()  # type: ignore[assignment]
            engine.executor.firmware_deployer = ForbiddenDeployer()  # type: ignore[assignment]
            run = engine.manual_run("firmware-smoke", "a" * 40, "main")
            while engine.tick():
                pass
            completed = database.gate_run(run["id"])

            self.assertEqual(completed["status"], "error")
            self.assertEqual(
                {item["status"] for item in completed["assignments"]}, {"error"}
            )
            self.assertTrue(
                all(
                    "testcode install failed" in item["detail"]
                    for item in completed["assignments"]
                )
            )
            database.close()

    def test_resource_leases_are_exclusive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = validate_config(configuration(root))
            database = OrchestratorDatabase(root / "state.sqlite3")
            event, _ = database.create_event(
                event_key="manual:1",
                repository_id="firmware",
                trigger_type="manual",
                commit_sha="b" * 40,
            )
            Planner(database).plan(config)
            first, second = database.assignments(database.list_gate_runs()[0]["id"])
            self.assertTrue(database.acquire(first["id"], ["device:bonanza"]))
            self.assertFalse(database.acquire(second["id"], ["device:bonanza"]))
            database.finish_assignment(first["id"], status="passed")
            self.assertTrue(database.acquire(second["id"], ["device:bonanza"]))
            database.close()


class OperatorUiTest(unittest.TestCase):
    def test_marks_only_safe_terminal_gate_runs_as_retryable(self) -> None:
        document = configuration(Path("/tmp/mining-qa-lab-ui-test"))
        snapshot = SimpleNamespace(
            document=document,
            revision="a" * 64,
            etag='"config-test"',
        )
        runs = [
            {
                "id": f"{status}-run",
                "gate_id": "firmware-smoke",
                "trigger_type": "manual",
                "commit_sha": "b" * 40,
                "pr_number": None,
                "status": status,
            }
            for status in (
                "failed",
                "error",
                "cancelled",
                "passed",
                "queued",
                "running",
                "superseded",
            )
        ]

        page = render_page("overview", snapshot, runs=runs)
        bootstrap_match = re.search(
            r'<script id="bootstrap" type="application/json">(.*?)</script>', page
        )

        self.assertIsNotNone(bootstrap_match)
        bootstrap = json.loads(bootstrap_match.group(1))
        by_status = {item["status"]: item for item in bootstrap["runs"]}
        self.assertTrue(by_status["failed"]["retryable"])
        self.assertTrue(by_status["error"]["retryable"])
        self.assertTrue(by_status["cancelled"]["retryable"])
        for status in ("passed", "queued", "running", "superseded"):
            self.assertFalse(by_status[status]["retryable"])
        self.assertIn('data-action="retry-run"', page)
        self.assertIn("Retry incomplete assignments", page)


class FakeTransport:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def json_request(self, method, url, body, *, token=None, headers=None, timeout=20):
        self.calls.append({"method": method, "url": url, "body": body, "token": token})
        if url.endswith("/results"):
            return {"linked": True}
        return {"run": {"id": "gate-qa-id"}}

    def put_file(self, *args, **kwargs):
        raise AssertionError("gate publisher must not upload child artifacts")


class GatePublisherTest(unittest.TestCase):
    def test_publishes_only_gate_and_links_existing_result(self) -> None:
        transport = FakeTransport()
        publisher = GatePublisher(
            {
                "enabled": True,
                "base_url": "https://qa.example",
                "token_env": "TEST_QA_TOKEN",
            },
            transport=transport,
        )
        run = {
            "id": "gate-run-1",
            "gate_id": "firmware-smoke",
            "repository_id": "firmware",
            "commit_sha": "a" * 40,
            "branch": "main",
            "pr_number": None,
            "trigger_type": "push",
            "definition_digest": "b" * 64,
            "required_policy": "all",
            "status": "passed",
            "summary": "1/1 assignments passed",
            "requested_by": "alice",
            "event_payload": {"approval_source": "local_control_plane"},
            "started_at": 1.0,
            "finished_at": 2.0,
        }
        assignment = {
            "id": "assignment-1",
            "setup_id": "bench",
            "module_id": "smoke",
            "platform_key": "bitaxe-bonanza-1002",
            "status": "passed",
            "qa_result_id": "child-id",
            "qa_result_url": "https://qa.example/results/child-id",
        }
        with mock.patch.dict("os.environ", {"TEST_QA_TOKEN": "secret"}):
            published = publisher.publish_run(
                run,
                gate={"name": "Firmware smoke"},
                repository={"repository": "owner/firmware"},
                assignments=[assignment],
            )
            publisher.link_result("gate-qa-id", assignment, "child-id")

        self.assertEqual(published["id"], "gate-qa-id")
        self.assertEqual(transport.calls[0]["body"]["platforms"], ["bitaxe-bonanza-1002"])
        self.assertEqual(
            transport.calls[0]["body"]["details"]["request"],
            {
                "requested_by": "alice",
                "authorization_source": "local_control_plane",
                "repository_id": "firmware",
                "device_types": [],
                "source_resolution": None,
            },
        )
        self.assertEqual(transport.calls[1]["body"]["result_id"], "child-id")
        self.assertEqual(len(transport.calls), 2)


if __name__ == "__main__":
    unittest.main()
