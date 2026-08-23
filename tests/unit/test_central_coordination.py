from __future__ import annotations

import json
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
    CentralAgent,
    CentralSettings,
    _stable_id,
    canonical_digest,
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
                        "base_url": "https://status.example",
                        "lab_id": "lab-east",
                        "subscriptions": {"gates": ["firmware-advisory"]},
                    },
                },
                "bindings": {
                    "suite_requirements": {
                        "gamma-http-and-stratum": {
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
            attempts = reopened.central_attempts("execution-1")
            self.assertEqual(len(attempts), 2)
            self.assertEqual(attempts[0]["state"], "error")
            self.assertTrue(reopened.central_agent_status()["paused"])
            self.assertEqual(reopened.central_outbox("execution-1")["state"], "pending")
            reopened.close()

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

    def test_active_runner_renews_claim_without_exposing_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state_dir = root / "state"
            state_dir.mkdir()
            profile = root / "profile.toml"
            profile.write_text("", encoding="utf-8")
            database = OrchestratorDatabase(state_dir / "orchestrator.sqlite3")
            value = offer()
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
                "profile": str(profile),
                "testcode_root": str(root),
                "mock_base_url_env": "TEST_MOCK_URL",
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
                state_dir / "central-artifacts" / "execution-1" / "result-pointer.json"
            )
            pointer_path.parent.mkdir(parents=True)
            pointer_path.write_text(
                json.dumps(
                    {
                        "contract_version": 2,
                        "run_id": "runner-1",
                        "status": "passed",
                        "publishers": [
                            {
                                "name": "mining_qa_status",
                                "success": True,
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
                def __init__(self, args, *, stdout, stderr, **_kwargs):
                    self.args = args
                    self.returncode = None
                    self.waits = 0
                    stdout.write(b"private stdout\n")
                    stderr.write(b"private stderr\n")

                def wait(self, timeout=None):
                    self.waits += 1
                    if self.waits == 1:
                        raise subprocess.TimeoutExpired(self.args, timeout)
                    self.returncode = 0
                    return 0

                def kill(self):
                    self.returncode = -9

            agent._preflight = Mock(return_value=(root, profile, "a" * 40, "main"))
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
