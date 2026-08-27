from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from mining_qa_lab.central import (
    MAX_RUNNER_OUTPUT_BYTES,
    CentralAgent,
    CentralSettings,
    RunnerPreflight,
    _stable_id,
    canonical_digest,
    register_central_lab,
    run_central_forever,
    validate_offer,
)
from mining_qa_lab.config import validate_config
from mining_qa_lab.database import OrchestratorDatabase
from mining_qa_lab.errors import ConfigError


BINDING_FIELDS = {
    "platform_class": "gamma-600",
    "device_model": "Gamma 602",
    "capabilities": ["api", "pool-config", "stratum-v1"],
    "resources": ["mock:gamma-602"],
    "testcode_commit": "a" * 40,
}


def definition() -> dict:
    return {
        "project": {"id": "firmware", "repository": "owner/firmware"},
        "gate": {"id": "firmware-advisory", "revision_id": "gate-rev-1"},
        "suite": {
            "id": "mock-smoke",
            "revision_id": "suite-rev-1",
            "requirements": [
                {
                    "requirement_id": "gamma-http-and-stratum",
                    "platform_class": "gamma-600",
                    "device_model": "Gamma 602",
                    "capabilities": ["api", "pool-config", "stratum-v1"],
                    "test_pattern": "test_integration_smoke.py",
                }
            ],
        },
        "trigger": {"id": "manual-local", "revision_id": "trigger-rev-1", "type": "manual"},
    }


def offer() -> dict:
    portable = definition()
    return {
        "central_gate_run_id": "run-1",
        "lab_execution_id": "execution-1",
        "lab_id": "lab-east",
        "public_lab_label": "East Lab",
        "platform_class": "gamma-600",
        "device_model": "Gamma 602",
        "definition_digest": canonical_digest(portable),
        "definition": portable,
        "source": {
            "repository": "owner/firmware",
            "commit_sha": "a" * 40,
            "ref_name": "main",
            "pr_number": None,
        },
        "offered_at": datetime.now(UTC).isoformat(),
        "deadline_at": (datetime.now(UTC) + timedelta(minutes=5)).isoformat(),
        "claim_ttl_seconds": 30,
        "max_claim_generations": 2,
    }


class CentralConfigurationTest(unittest.TestCase):
    @staticmethod
    def central_document(root: Path) -> dict:
        return {
            "schema_version": 1,
            "controller": {"state_dir": str(root / "state")},
            "coordination": {
                "mode": "central",
                "central": {
                    "base_url": "http://127.0.0.1:3000",
                    "lab_id": "lab-east",
                    "token_env": "TEST_LAB_TOKEN",
                    "subscriptions": {"gates": ["firmware-advisory"]},
                },
            },
            "bindings": {
                "suite_requirements": {
                    "gamma-http-and-stratum": {
                        "execution": "mock",
                        "profile": str(root / "profile.toml"),
                        "testcode_root": str(root / "testcode"),
                        "mock_base_url_env": "TEST_MOCK_URL",
                        **BINDING_FIELDS,
                    }
                }
            },
        }

    def test_central_mode_requires_loopback_or_https_and_private_binding(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = {
                "schema_version": 1,
                "controller": {"state_dir": str(root / "state")},
                "coordination": {
                    "mode": "central",
                    "central": {
                        "base_url": "http://127.0.0.1:3000",
                        "lab_id": "lab-east",
                        "token_env": "TEST_LAB_TOKEN",
                        "subscriptions": {"gates": ["firmware-advisory"]},
                    },
                },
                "bindings": {
                    "suite_requirements": {
                        "gamma-http-and-stratum": {
                            "execution": "mock",
                            "profile": str(root / "profile.toml"),
                            "testcode_root": str(root / "testcode"),
                            "mock_base_url_env": "TEST_MOCK_URL",
                            **BINDING_FIELDS,
                        }
                    }
                },
            }
            normalized = validate_config(document)
            self.assertEqual(normalized["coordination"]["mode"], "central")

            document["coordination"]["central"]["base_url"] = "https://status.example"
            with self.assertRaisesRegex(ConfigError, "loopback central Status"):
                validate_config(document)

            document["coordination"]["central"]["base_url"] = "http://status.example"
            with self.assertRaisesRegex(ConfigError, "HTTPS"):
                validate_config(document)

    def test_central_mode_cannot_merge_local_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = {
                "schema_version": 1,
                "controller": {"state_dir": str(root / "state")},
                "coordination": {
                    "mode": "central",
                    "central": {
                        "base_url": "http://127.0.0.1:3000",
                        "lab_id": "lab-east",
                        "subscriptions": {"gates": ["firmware-advisory"]},
                    },
                },
                "bindings": {
                    "suite_requirements": {
                        "gamma-http-and-stratum": {
                            "execution": "mock",
                            "profile": str(root / "profile.toml"),
                            "testcode_root": str(root / "testcode"),
                            **BINDING_FIELDS,
                        }
                    }
                },
                "repositories": {"local": {"repository": "owner/local"}},
            }
            with self.assertRaisesRegex(ConfigError, "cannot merge"):
                validate_config(document)

    def test_binding_execution_mode_is_explicit_and_disjoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self.central_document(root)
            binding = document["bindings"]["suite_requirements"][
                "gamma-http-and-stratum"
            ]
            binding.pop("execution")
            with self.assertRaisesRegex(ConfigError, "must be mock or hardware"):
                validate_config(document)

            binding["execution"] = "hardware"
            binding.pop("mock_base_url_env")
            binding["runner_executable"] = str(root / "venv/bin/miner-test")
            binding["runner_devices"] = ["gamma-02"]
            normalized = validate_config(document)
            normalized_binding = normalized["bindings"]["suite_requirements"][
                "gamma-http-and-stratum"
            ]
            self.assertEqual(normalized_binding["execution"], "hardware")
            self.assertEqual(normalized_binding["timeout_seconds"], 3600)

            binding["mock_base_url_env"] = "TEST_MOCK_URL"
            with self.assertRaisesRegex(ConfigError, "cannot configure a mock endpoint"):
                validate_config(document)

    def test_central_credential_can_be_the_runner_publisher_token(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            document = self.central_document(root)
            document["controller"]["environment_allowlist"] = ["TEST_LAB_TOKEN"]
            normalized = validate_config(document)
            self.assertEqual(
                normalized["coordination"]["central"]["token_env"],
                "TEST_LAB_TOKEN",
            )


class CentralContractTest(unittest.TestCase):
    def test_offer_validation_is_strict_and_digest_bound(self) -> None:
        value = offer()
        self.assertEqual(validate_offer(value, "lab-east"), value)

        private = {**value, "private_canary": "device-canary-east"}
        with self.assertRaisesRegex(ValueError, "invalid fields"):
            validate_offer(private, "lab-east")

        mismatched = {**value, "definition_digest": "b" * 64}
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            validate_offer(mismatched, "lab-east")

        for remote in (
            "git@github.com:johnny9/mining-qa-testcode.git",
            "ssh://git@github.com/johnny9/mining-qa-testcode.git",
            "https://github.com/johnny9/mining-qa-testcode.git",
        ):
            self.assertEqual(
                CentralAgent._repository_from_remote(remote),
                "johnny9/mining-qa-testcode",
            )
        self.assertIsNone(
            CentralAgent._repository_from_remote(
                "https://token@github.com/johnny9/mining-qa-testcode.git"
            )
        )

    def test_offer_accepts_catalog_modules_options_and_repository_triggers(self) -> None:
        value = offer()
        value["definition"]["suite"]["testcode_catalog"] = {
            "repository": "johnny9/mining-qa-testcode",
            "ref": "main",
            "commit_sha": "a" * 40,
        }
        requirement = value["definition"]["suite"]["requirements"][0]
        requirement["module_id"] = "public_pool_smoke"
        requirement["options"] = {"stable_samples": 4, "require_accepted_share": True}
        value["definition"]["trigger"]["type"] = "push"
        value["definition_digest"] = canonical_digest(value["definition"])

        self.assertEqual(validate_offer(value, "lab-east"), value)

        settings = CentralSettings(
            base_url="http://127.0.0.1:3000",
            lab_id="lab-east",
            token="private-agent-token",
            timeout=1,
            subscriptions=("firmware-advisory",),
            state_dir=Path("/tmp/unused-central-test"),
            bindings={"gamma-http-and-stratum": dict(BINDING_FIELDS)},
            heartbeat_seconds=30,
            poll_seconds=1,
            retry_backoff_seconds=1,
            max_retry_backoff_seconds=2,
            max_attempts=1,
        )
        agent = CentralAgent.__new__(CentralAgent)
        agent.settings = settings
        self.assertIsNotNone(agent._binding(value))
        value["definition"]["suite"]["testcode_catalog"]["commit_sha"] = "b" * 40
        self.assertIsNone(agent._binding(value))

        unsafe = offer()
        unsafe_requirement = unsafe["definition"]["suite"]["requirements"][0]
        unsafe_requirement["module_id"] = "public_pool_smoke"
        unsafe_requirement["options"] = {"password": "private"}
        unsafe["definition_digest"] = canonical_digest(unsafe["definition"])
        with self.assertRaisesRegex(ValueError, "private or unsafe"):
            validate_offer(unsafe, "lab-east")

    def test_cursor_offer_attempt_and_outbox_survive_reopen_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "orchestrator.sqlite3"
            database = OrchestratorDatabase(path)
            value = offer()
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[value])
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[value])
            _, created = database.start_central_attempt(
                execution_id="execution-1",
                assignment_id="assignment-1",
                attempt_id="attempt-1",
                started_at=datetime.now(UTC).isoformat(),
            )
            self.assertTrue(created)
            _, replay_created = database.start_central_attempt(
                execution_id="execution-1",
                assignment_id="assignment-1",
                attempt_id="attempt-1",
                started_at=datetime.now(UTC).isoformat(),
            )
            self.assertFalse(replay_created)
            database.finish_central_attempt(
                attempt_id="attempt-1",
                state="error",
                completed_at=datetime.now(UTC).isoformat(),
                pointer={"status": "error"},
                cleanup_disposition="restored",
            )
            second, second_created = database.start_central_attempt(
                execution_id="execution-1",
                assignment_id="assignment-1",
                attempt_id="attempt-2",
                started_at=datetime.now(UTC).isoformat(),
            )
            self.assertTrue(second_created)
            self.assertEqual(second["attempt"], 2)
            self.assertTrue(
                database.acquire_central_resources(
                    "execution-1", "assignment-1", ["mock:gamma-602"]
                )
            )
            self.assertTrue(database.central_agent_status()["active_leases"])
            frozen_binding = database.freeze_central_binding(
                "execution-1",
                {"execution": "mock", "resources": ["mock:gamma-602"]},
            )
            self.assertEqual(frozen_binding["execution"], "mock")
            with self.assertRaisesRegex(ValueError, "changed after it was frozen"):
                database.freeze_central_binding(
                    "execution-1",
                    {"execution": "hardware", "resources": ["device:gamma-02"]},
                )
            self.assertTrue(database.set_central_agent_paused(True)["paused"])
            database.enqueue_central_completion(
                execution_id="execution-1",
                idempotency_key="complete-1",
                body={"contract_version": 2},
            )
            database.close()

            reopened = OrchestratorDatabase(path)
            self.assertEqual(reopened.cursor("central:lab-east")["value"], "1")
            self.assertEqual(len(reopened.pending_central_executions("lab-east")), 1)
            self.assertEqual(
                reopened.central_execution("execution-1")["binding"], frozen_binding
            )
            attempts = reopened.central_attempts("execution-1")
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["state"], "error")
            self.assertTrue(reopened.central_agent_status()["paused"])
            self.assertEqual(reopened.central_outbox("execution-1")["state"], "pending")
            reopened.close()

    def test_central_attempt_limit_is_per_requirement_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "orchestrator.sqlite3")
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[offer()])
            database.start_central_attempt(
                execution_id="execution-1",
                assignment_id="assignment-module-a",
                attempt_id="attempt-module-a-1",
                started_at=datetime.now(UTC).isoformat(),
                max_attempts=1,
            )
            second, created = database.start_central_attempt(
                execution_id="execution-1",
                assignment_id="assignment-module-b",
                attempt_id="attempt-module-b-1",
                started_at=datetime.now(UTC).isoformat(),
                max_attempts=1,
            )
            self.assertTrue(created)
            self.assertEqual(second["attempt"], 2)
            with self.assertRaisesRegex(ValueError, "central assignment exceeded"):
                database.start_central_attempt(
                    execution_id="execution-1",
                    assignment_id="assignment-module-a",
                    attempt_id="attempt-module-a-2",
                    started_at=datetime.now(UTC).isoformat(),
                    max_attempts=1,
                )
            database.close()

    def test_multi_module_plan_resumes_completed_module_and_publishes_all_children(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = OrchestratorDatabase(root / "orchestrator.sqlite3")
            value = offer()
            second_requirement = {
                "requirement_id": "gamma-api-regression",
                "platform_class": "gamma-600",
                "device_model": "Gamma 602",
                "capabilities": ["api"],
                "test_pattern": "test_api_regression.py",
            }
            value["definition"]["suite"]["requirements"].append(second_requirement)
            value["definition_digest"] = canonical_digest(value["definition"])
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[value])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            bindings = {
                "gamma-http-and-stratum": {
                    "execution": "mock",
                    "testcode_commit": "a" * 40,
                    **BINDING_FIELDS,
                },
                "gamma-api-regression": {
                    "execution": "mock",
                    "testcode_commit": "a" * 40,
                    **BINDING_FIELDS,
                },
            }
            settings = CentralSettings(
                base_url="http://127.0.0.1:3000",
                lab_id="lab-east",
                token="private-agent-token",
                timeout=1,
                subscriptions=("firmware-advisory",),
                state_dir=root,
                bindings=bindings,
                heartbeat_seconds=30,
                poll_seconds=1,
                retry_backoff_seconds=0.001,
                max_retry_backoff_seconds=0.002,
                max_attempts=2,
            )
            agent = CentralAgent(settings, database)
            binding_plan = agent._binding(value)
            self.assertIsNotNone(binding_plan)
            self.assertEqual(
                [item["requirement"]["requirement_id"] for item in binding_plan["items"]],
                ["gamma-http-and-stratum", "gamma-api-regression"],
            )
            assignment_a = agent._assignment_id(
                "execution-1",
                value["definition"]["suite"]["requirements"][0],
                2,
            )
            attempt_a = _stable_id("attempt", f"{assignment_a}:1")

            def pointer(assignment_id: str, attempt_id: str, suffix: str, status: str) -> dict:
                return {
                    "contract_version": 2,
                    "run_id": f"runner-{suffix}",
                    "successful": status in {"passed", "skipped"},
                    "status": status,
                    "publishers": [
                        {
                            "name": "mining_qa_status",
                            "success": True,
                            "required": True,
                            "result_id": f"child-{suffix}",
                            "url": f"http://127.0.0.1:3000/results/child-{suffix}",
                        }
                    ],
                    "correlation": {
                        "central_gate_run_id": "run-1",
                        "lab_id": "lab-east",
                        "lab_execution_id": "execution-1",
                        "local_gate_run_id": _stable_id("local", "execution-1"),
                        "assignment_id": assignment_id,
                        "attempt_id": attempt_id,
                        "definition_digest": value["definition_digest"],
                    },
                }

            started_a = datetime.now(UTC).isoformat()
            database.start_central_attempt(
                execution_id="execution-1",
                assignment_id=assignment_a,
                attempt_id=attempt_a,
                started_at=started_a,
            )
            database.finish_central_attempt(
                attempt_id=attempt_a,
                state="passed",
                completed_at=started_a,
                pointer=pointer(assignment_a, attempt_a, "module-a", "passed"),
                cleanup_disposition="restored",
            )
            agent._renew = Mock()
            agent._preflight = Mock(
                return_value=RunnerPreflight(
                    root,
                    root / "profile.toml",
                    None,
                    "a" * 40,
                    "main",
                )
            )
            agent._flush = Mock(return_value="completed")

            def run_second(_execution, _binding, _behavior, requirement, assignment_id):
                self.assertEqual(requirement["requirement_id"], "gamma-api-regression")
                attempt_id = _stable_id("attempt", f"{assignment_id}:1")
                started_at = datetime.now(UTC).isoformat()
                database.start_central_attempt(
                    execution_id="execution-1",
                    assignment_id=assignment_id,
                    attempt_id=attempt_id,
                    started_at=started_at,
                )
                completed_at = datetime.now(UTC).isoformat()
                result_pointer = pointer(
                    assignment_id,
                    attempt_id,
                    "module-b",
                    "failed",
                )
                database.finish_central_attempt(
                    attempt_id=attempt_id,
                    state="failed",
                    completed_at=completed_at,
                    pointer=result_pointer,
                    cleanup_disposition="restored",
                )
                return result_pointer, started_at, completed_at, "a" * 40, "main"

            agent._run_testcode = Mock(side_effect=run_second)
            outcome = agent._execute_with_lease(
                database.central_execution("execution-1"),
                binding_plan,
                phase="run",
                behavior="pass",
            )

            self.assertEqual(outcome, "completed")
            agent._run_testcode.assert_called_once()
            completion = database.central_outbox("execution-1")["body"]
            self.assertEqual(completion["published_completion"]["outcome"], "failed")
            self.assertEqual(
                [child["result_id"] for child in completion["published_completion"]["children"]],
                ["child-module-a", "child-module-b"],
            )
            database.close()

    def test_durable_outbox_flush_precedes_mutable_binding_and_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "orchestrator.sqlite3")
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[offer()])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            database.enqueue_central_completion(
                execution_id="execution-1",
                idempotency_key="complete-execution-1",
                body={"contract_version": 2},
            )
            agent = CentralAgent.__new__(CentralAgent)
            agent.settings = SimpleNamespace(lab_id="lab-east")
            agent.database = database
            agent.announce = Mock()
            agent.pull = Mock(return_value=[])
            agent._flush = Mock(return_value="completed")
            agent._binding = Mock(side_effect=AssertionError("binding must not be read"))
            agent._preflight = Mock(side_effect=AssertionError("preflight must not run"))

            self.assertEqual(agent.process(phase="run", behavior="pass"), ["completed"])
            agent._flush.assert_called_once()
            agent._binding.assert_not_called()
            agent._preflight.assert_not_called()
            database.close()

    def test_process_releases_private_resources_when_claim_path_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "orchestrator.sqlite3")
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[offer()])
            agent = CentralAgent.__new__(CentralAgent)
            agent.settings = SimpleNamespace(lab_id="lab-east")
            agent.database = database
            agent.announce = Mock()
            agent.pull = Mock(return_value=[])
            binding = {"resources": ["mock:gamma-602"]}
            agent._binding = Mock(return_value=binding)
            agent._preflight = Mock()
            agent._execute_with_lease = Mock(side_effect=ConfigError("claim failed"))

            with self.assertRaisesRegex(ConfigError, "claim failed"):
                agent.process(phase="run", behavior="pass")
            self.assertEqual(database.central_agent_status()["active_leases"], 0)
            database.close()

    def test_capacity_decline_includes_an_existing_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "orchestrator.sqlite3")
            blocker = offer()
            blocker["central_gate_run_id"] = "run-2"
            blocker["lab_execution_id"] = "execution-2"
            database.persist_central_page(
                lab_id="lab-east", cursor="1", offers=[blocker]
            )
            self.assertTrue(
                database.acquire_central_resources(
                    "execution-2", "assignment-2", ["device:gamma-02"]
                )
            )
            database.update_central_execution("execution-2", state="completed")
            database.persist_central_page(
                lab_id="lab-east", cursor="2", offers=[offer()]
            )
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            binding = {
                "execution": "hardware",
                "resources": ["device:gamma-02"],
            }
            agent = CentralAgent.__new__(CentralAgent)
            agent.settings = SimpleNamespace(lab_id="lab-east")
            agent.database = database
            agent.announce = Mock()
            agent.pull = Mock(return_value=[])
            agent._binding = Mock(return_value=binding)
            agent._preflight = Mock()
            agent._decline = Mock()

            self.assertEqual(agent.process(phase="run", behavior="pass"), ["declined"])
            declined_execution = agent._decline.call_args.kwargs["execution"]
            self.assertEqual(declined_execution["state"], "claimed")
            self.assertEqual(declined_execution["claim_id"], "claim-1")
            database.close()

    def test_active_runner_renews_claim_without_exposing_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            state_dir.mkdir()
            profile = root / "profile.toml"
            profile.write_text("", encoding="utf-8")
            database = OrchestratorDatabase(state_dir / "orchestrator.sqlite3")
            value = offer()
            value["definition"]["suite"]["testcode_catalog"] = {
                "repository": "johnny9/mining-qa-testcode",
                "ref": "main",
                "commit_sha": "a" * 40,
            }
            value["definition"]["suite"]["requirements"][0].update(
                {
                    "module_id": "public_pool_smoke",
                    "options": {"stable_samples": 4},
                }
            )
            value["definition_digest"] = canonical_digest(value["definition"])
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[value])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
            )
            binding = {
                "execution": "mock",
                "profile": str(profile),
                "testcode_root": str(root),
                "mock_base_url_env": "TEST_MOCK_URL",
                "timeout_seconds": 60,
                **BINDING_FIELDS,
            }
            settings = CentralSettings(
                base_url="http://127.0.0.1:3000",
                lab_id="lab-east",
                token="private-agent-token",
                timeout=1,
                subscriptions=("firmware-advisory",),
                state_dir=state_dir,
                bindings={"gamma-http-and-stratum": binding},
                heartbeat_seconds=30,
                poll_seconds=1,
                retry_backoff_seconds=1,
                max_retry_backoff_seconds=2,
                max_attempts=3,
            )
            agent = CentralAgent(settings, database)
            execution = database.central_execution("execution-1")
            assignment_id = _stable_id("assignment", "execution-1")
            attempt_id = _stable_id("attempt", "execution-1:1")
            pointer_path = (
                state_dir
                / "central-artifacts"
                / "execution-1"
                / "attempt-1"
                / "result-pointer.json"
            )
            pointer_path.parent.mkdir(parents=True)
            pointer_path.write_text(
                json.dumps(
                    {
                        "contract_version": 2,
                        "run_id": "runner-1",
                        "successful": True,
                        "status": "passed",
                        "publishers": [
                            {
                                "name": "mining_qa_status",
                                "success": True,
                                "required": True,
                                "result_id": "child-result-1",
                                "url": "http://127.0.0.1:3000/results/child-result-1",
                            }
                        ],
                        "correlation": {
                            "central_gate_run_id": "run-1",
                            "lab_id": "lab-east",
                            "lab_execution_id": "execution-1",
                            "local_gate_run_id": _stable_id("local", "execution-1"),
                            "assignment_id": assignment_id,
                            "attempt_id": attempt_id,
                            "definition_digest": value["definition_digest"],
                        },
                    }
                ),
                encoding="utf-8",
            )

            class FakeProcess:
                def __init__(self, args, **_kwargs):
                    self.args = args
                    self.returncode = None
                    self.waits = 0
                    self.stdout = io.BytesIO(b"private stdout\n")
                    self.stderr = io.BytesIO(b"private stderr\n")

                def wait(self, timeout=None):
                    self.waits += 1
                    if self.waits == 1:
                        raise subprocess.TimeoutExpired(self.args, timeout)
                    self.returncode = 0
                    return 0

                def kill(self):
                    self.returncode = -9

            agent._preflight = Mock(
                return_value=RunnerPreflight(
                    root=root,
                    profile=profile,
                    executable=None,
                    sha="a" * 40,
                    ref="main",
                )
            )
            agent._renew = Mock()
            with (
                patch("mining_qa_lab.central.subprocess.Popen", FakeProcess),
                patch("mining_qa_lab.central.CoordinationClient.request", return_value={}),
                patch.dict("os.environ", {"TEST_MOCK_URL": "http://127.0.0.1:39001"}),
            ):
                pointer, *_ = agent._run_testcode(execution, binding, "pass")

            self.assertEqual(pointer["status"], "passed")
            agent._renew.assert_called_once()
            attempts = database.central_attempts("execution-1")
            self.assertEqual((attempts[0]["attempt_id"], attempts[0]["state"]), (attempt_id, "passed"))
            private = pointer_path.parent / ".private"
            self.assertIn("private stdout", (private / "attempt-1.stdout.raw.log").read_text())
            database.close()

    def test_hardware_runner_uses_private_devices_portable_pattern_and_allowlisted_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            state_dir.mkdir()
            profile = root / "hardware.toml"
            profile.write_text("", encoding="utf-8")
            executable = root / "venv/bin/miner-test"
            executable.parent.mkdir(parents=True)
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o700)
            database = OrchestratorDatabase(state_dir / "orchestrator.sqlite3")
            value = offer()
            value["definition"]["suite"]["testcode_catalog"] = {
                "repository": "johnny9/mining-qa-testcode",
                "ref": "main",
                "commit_sha": "a" * 40,
            }
            value["definition"]["suite"]["requirements"][0].update(
                {
                    "module_id": "public_pool_smoke",
                    "options": {"stable_samples": 4},
                }
            )
            value["definition_digest"] = canonical_digest(value["definition"])
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[value])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            binding = {
                "execution": "hardware",
                "profile": str(profile),
                "testcode_root": str(root),
                "runner_executable": str(executable),
                "runner_devices": ["gamma-02", "stratum-probe"],
                "timeout_seconds": 120,
                **BINDING_FIELDS,
            }
            settings = CentralSettings(
                base_url="http://127.0.0.1:3000",
                lab_id="lab-east",
                token="central-agent-secret",
                timeout=1,
                subscriptions=("firmware-advisory",),
                state_dir=state_dir,
                bindings={"gamma-http-and-stratum": binding},
                heartbeat_seconds=30,
                poll_seconds=1,
                retry_backoff_seconds=1,
                max_retry_backoff_seconds=2,
                max_attempts=3,
                environment_allowlist=("DEVICE_API_TOKEN",),
                token_environment="TEST_LAB_TOKEN",
            )
            agent = CentralAgent(settings, database)
            execution = database.central_execution("execution-1")
            assignment_id = _stable_id("assignment", "execution-1")
            attempt_id = _stable_id("attempt", "execution-1:1")
            pointer_path = (
                state_dir
                / "central-artifacts/execution-1/attempt-1/result-pointer.json"
            )
            pointer_path.parent.mkdir(parents=True)
            pointer_path.write_text(
                json.dumps(
                    {
                        "contract_version": 2,
                        "run_id": "runner-hardware-1",
                        "successful": True,
                        "status": "passed",
                        "publishers": [
                            {
                                "name": "mining_qa_status",
                                "success": True,
                                "required": True,
                                "result_id": "child-result-1",
                                "url": "http://127.0.0.1:3000/results/child-result-1",
                            }
                        ],
                        "correlation": {
                            "central_gate_run_id": "run-1",
                            "lab_id": "lab-east",
                            "lab_execution_id": "execution-1",
                            "local_gate_run_id": _stable_id("local", "execution-1"),
                            "assignment_id": assignment_id,
                            "attempt_id": attempt_id,
                            "definition_digest": value["definition_digest"],
                        },
                    }
                ),
                encoding="utf-8",
            )
            invocations: list[dict] = []

            class FakeProcess:
                def __init__(self, args, **kwargs):
                    invocations.append({"args": args, **kwargs})
                    self.returncode = 0
                    self.stdout = io.BytesIO(b"hardware output\n")
                    self.stderr = io.BytesIO()

                def wait(self, timeout=None):
                    return 0

                def kill(self):
                    self.returncode = -9

            agent._preflight = Mock(
                return_value=RunnerPreflight(
                    root=root,
                    profile=profile,
                    executable=executable,
                    sha="a" * 40,
                    ref="main",
                )
            )
            with (
                patch("mining_qa_lab.central.subprocess.Popen", FakeProcess),
                patch.dict(
                    os.environ,
                    {
                        "PATH": "/usr/bin",
                        "MINING_QA_TOKEN": "stale-publisher-secret",
                        "TEST_LAB_TOKEN": "central-agent-secret",
                        "DEVICE_API_TOKEN": "device-api-secret",
                        "UNRELATED_SECRET": "must-not-pass",
                        "MINING_QA_MOCK_URL": "http://127.0.0.1:39001",
                    },
                    clear=True,
                ),
            ):
                pointer, *_ = agent._run_testcode(execution, binding, "pass")

            self.assertEqual(pointer["status"], "passed")
            self.assertEqual(
                invocations[0]["args"],
                [
                    str(executable),
                    "--config",
                    str(profile),
                    "--pattern",
                    "test_integration_smoke.py",
                    "--device",
                    "gamma-02",
                    "--device",
                    "stratum-probe",
                ],
            )
            runner_environment = invocations[0]["env"]
            self.assertEqual(runner_environment["DEVICE_API_TOKEN"], "device-api-secret")
            self.assertEqual(
                runner_environment["MINING_QA_TOKEN"], "central-agent-secret"
            )
            self.assertNotIn("TEST_LAB_TOKEN", runner_environment)
            self.assertNotIn("UNRELATED_SECRET", runner_environment)
            self.assertNotIn("MINING_QA_MOCK_URL", runner_environment)
            self.assertNotIn("MINING_QA_INTEGRATION_DEVELOPMENT", runner_environment)
            self.assertEqual(
                json.loads(runner_environment["MINER_TEST_MODULE_OPTIONS"]),
                {
                    "schema_version": 1,
                    "module_id": "public_pool_smoke",
                    "values": {"stable_samples": 4},
                },
            )
            database.close()

    def test_hardware_failure_is_terminal_without_automatic_retry(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = OrchestratorDatabase(root / "orchestrator.sqlite3")
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[offer()])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            binding = {
                "execution": "hardware",
                "resources": ["device:gamma-02"],
            }
            settings = CentralSettings(
                base_url="http://127.0.0.1:3000",
                lab_id="lab-east",
                token="private-agent-token",
                timeout=1,
                subscriptions=("firmware-advisory",),
                state_dir=root,
                bindings={"gamma-http-and-stratum": binding},
                heartbeat_seconds=30,
                poll_seconds=1,
                retry_backoff_seconds=0.001,
                max_retry_backoff_seconds=0.002,
                max_attempts=3,
            )
            agent = CentralAgent(settings, database)
            target = RunnerPreflight(root, root / "profile.toml", root / "miner-test", "a" * 40, "main")
            agent._preflight = Mock(return_value=target)
            agent._renew = Mock()
            agent._flush = Mock(return_value="completed")

            def fail_once(execution, _binding, _behavior):
                database.start_central_attempt(
                    execution_id="execution-1",
                    assignment_id=_stable_id("assignment", "execution-1"),
                    attempt_id=_stable_id("attempt", "execution-1:1"),
                    started_at=datetime.now(UTC).isoformat(),
                    max_attempts=3,
                )
                raise ConfigError("private device failure")

            agent._run_testcode = Mock(side_effect=fail_once)
            outcome = agent._execute_with_lease(
                database.central_execution("execution-1"),
                binding,
                phase="run",
                behavior="pass",
            )

            self.assertEqual(outcome, "completed")
            agent._run_testcode.assert_called_once()
            attempt = database.central_attempts("execution-1")[0]
            self.assertEqual(attempt["cleanup_disposition"], "uncertain")
            completion = database.central_outbox("execution-1")["body"]
            self.assertEqual(completion["published_completion"]["outcome"], "error")
            self.assertEqual(completion["published_completion"]["children"], [])
            self.assertEqual(
                completion["published_completion"]["reason_code"],
                "local_execution_error",
            )
            self.assertNotIn("private device failure", json.dumps(completion))
            database.close()

    def test_runner_output_capture_is_bounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = {"size": 0, "overflow": False}
            lock = threading.Lock()
            CentralAgent._drain_runner_stream(
                io.BytesIO(b"x" * (MAX_RUNNER_OUTPUT_BYTES + 100)),
                root / "stdout.log",
                state,
                lock,
            )
            CentralAgent._drain_runner_stream(
                io.BytesIO(b"y" * 100),
                root / "stderr.log",
                state,
                lock,
            )
            self.assertEqual(state["size"], MAX_RUNNER_OUTPUT_BYTES)
            self.assertTrue(state["overflow"])
            self.assertLessEqual(
                (root / "stdout.log").stat().st_size
                + (root / "stderr.log").stat().st_size,
                MAX_RUNNER_OUTPUT_BYTES,
            )

    def test_renewal_key_advances_only_after_observed_lease_progress(self) -> None:
        agent = CentralAgent.__new__(CentralAgent)
        agent.client = Mock(
            request=Mock(
                side_effect=[
                    {"lease_expires_at": "2026-08-24T12:02:00Z"},
                    {"lease_expires_at": "2026-08-24T12:02:00Z"},
                    {"lease_expires_at": "2026-08-24T12:03:00Z"},
                ]
            )
        )
        agent.database = Mock()
        execution = {
            "lab_execution_id": "execution-1",
            "claim_id": "claim-1",
            "claim_generation": 1,
            "claim_token": "private-claim-token",
            "claim_expires_at": "2026-08-24T12:01:00Z",
        }

        agent._renew(execution)
        agent._renew(execution)
        agent._renew({**execution, "claim_expires_at": "2026-08-24T12:02:00Z"})

        bodies = [call.args[2] for call in agent.client.request.call_args_list]
        self.assertEqual(bodies[0]["idempotency_key"], bodies[1]["idempotency_key"])
        self.assertNotEqual(bodies[1]["idempotency_key"], bodies[2]["idempotency_key"])

    def test_interrupted_hardware_attempt_is_completed_without_relaunch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = OrchestratorDatabase(root / "orchestrator.sqlite3")
            database.persist_central_page(lab_id="lab-east", cursor="1", offers=[offer()])
            database.update_central_execution(
                "execution-1",
                state="claimed",
                claim_id="claim-1",
                claim_generation=1,
                claim_token="private-claim-token",
                claim_expires_at=(datetime.now(UTC) + timedelta(minutes=2)).isoformat(),
            )
            database.start_central_attempt(
                execution_id="execution-1",
                assignment_id=_stable_id("assignment", "execution-1"),
                attempt_id=_stable_id("attempt", "execution-1:1"),
                started_at=datetime.now(UTC).isoformat(),
            )
            database.fail_running_central_attempt(
                "execution-1",
                "agent restarted while hardware state was unknown",
                cleanup_disposition="uncertain",
            )
            binding = {
                "execution": "hardware",
                "resources": ["device:gamma-02"],
                "testcode_commit": "a" * 40,
            }
            settings = CentralSettings(
                base_url="http://127.0.0.1:3000",
                lab_id="lab-east",
                token="private-agent-token",
                timeout=1,
                subscriptions=("firmware-advisory",),
                state_dir=root,
                bindings={"gamma-http-and-stratum": binding},
                heartbeat_seconds=30,
                poll_seconds=1,
                retry_backoff_seconds=0.001,
                max_retry_backoff_seconds=0.002,
                max_attempts=3,
            )
            agent = CentralAgent(settings, database)
            agent._preflight = Mock(
                return_value=RunnerPreflight(
                    root,
                    root / "profile.toml",
                    root / "miner-test",
                    "a" * 40,
                    "main",
                )
            )
            agent._renew = Mock()
            agent._run_testcode = Mock()
            agent._flush = Mock(return_value="completed")

            outcome = agent._execute_with_lease(
                database.central_execution("execution-1"),
                binding,
                phase="run",
                behavior="pass",
            )

            self.assertEqual(outcome, "completed")
            agent._run_testcode.assert_not_called()
            self.assertEqual(
                database.central_outbox("execution-1")["body"]["published_completion"][
                    "reason_code"
                ],
                "local_execution_error",
            )
            database.close()

    def test_registration_writes_only_a_mode_0600_agent_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "agent.env"
            document = CentralConfigurationTest.central_document(root)
            document = validate_config(document)
            store = SimpleNamespace(
                snapshot=SimpleNamespace(document=document),
            )
            response = {
                "contract_version": 2,
                "lab_id": "lab-east",
                "registration_id": "registration-lab-east-1",
                "credential_state": "bound",
                "issued_at": datetime.now(UTC).isoformat(),
            }
            lab_token = "mqa_" + "a" * 43
            with (
                patch.dict(
                    os.environ,
                    {"TEST_LAB_TOKEN": lab_token},
                    clear=True,
                ),
                patch(
                    "mining_qa_lab.central.CoordinationClient.request",
                    return_value=response,
                ) as request,
            ):
                result = register_central_lab(
                    store,
                    public_label="East Lab",
                    agent_environment_file=destination,
                )

            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                destination.read_text(encoding="utf-8"),
                f"TEST_LAB_TOKEN={lab_token}\n",
            )
            self.assertNotIn(lab_token, json.dumps(result))
            self.assertEqual(request.call_args.args[1], "/api/v2/labs/register")
            with self.assertRaisesRegex(ConfigError, "absolute non-root"):
                register_central_lab(
                    store,
                    public_label="East Lab",
                    agent_environment_file=Path("relative.env"),
                )

    def test_continuous_loop_honors_persisted_backoff_pause_and_heartbeat_cadence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = OrchestratorDatabase(Path(directory) / "orchestrator.sqlite3")
            settings = SimpleNamespace(
                poll_seconds=0.001,
                heartbeat_seconds=30,
                retry_backoff_seconds=0.001,
                max_retry_backoff_seconds=0.01,
            )
            database.record_central_agent_cycle(
                error="temporary outage",
                consecutive_failures=2,
                next_retry_at=time.time() + 0.02,
            )
            fake_agent = Mock()
            fake_agent.process.return_value = []
            started = time.monotonic()
            with (
                patch("mining_qa_lab.central.CentralSettings.from_store", return_value=settings),
                patch("mining_qa_lab.central.CentralAgent", return_value=fake_agent),
            ):
                cycles = run_central_forever(Mock(), database, max_cycles=2)
            self.assertEqual(cycles, 2)
            self.assertGreaterEqual(time.monotonic() - started, 0.015)
            self.assertEqual(
                [call.kwargs["announce"] for call in fake_agent.process.call_args_list],
                [True, False],
            )
            self.assertEqual(database.central_agent_status()["consecutive_failures"], 0)

            database.set_central_agent_paused(True)
            with (
                patch("mining_qa_lab.central.CentralSettings.from_store", return_value=settings),
                patch("mining_qa_lab.central.CentralAgent"),
            ):
                self.assertEqual(
                    run_central_forever(Mock(), database, stop=threading.Event(), max_cycles=1),
                    0,
                )
            database.close()


if __name__ == "__main__":
    unittest.main()
