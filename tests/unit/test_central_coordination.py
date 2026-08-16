from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from mining_qa_lab.central import canonical_digest, validate_offer
from mining_qa_lab.config import validate_config
from mining_qa_lab.database import OrchestratorDatabase
from mining_qa_lab.errors import ConfigError


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
            database.enqueue_central_completion(
                execution_id="execution-1",
                idempotency_key="complete-1",
                body={"contract_version": 2},
            )
            database.close()

            reopened = OrchestratorDatabase(path)
            self.assertEqual(reopened.cursor("central:lab-east")["value"], "1")
            self.assertEqual(len(reopened.pending_central_executions("lab-east")), 1)
            self.assertEqual(len(reopened.central_attempts("execution-1")), 1)
            self.assertEqual(reopened.central_outbox("execution-1")["state"], "pending")
            reopened.close()


if __name__ == "__main__":
    unittest.main()
