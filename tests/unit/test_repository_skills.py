from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SKILL_NAME = "manage-lab-orchestrator-deployment"
SKILL_ROOT = ROOT / "skills" / SKILL_NAME
SKILL_NAMES = (
    "add-mining-lab-device",
    "create-mining-qa-gate",
    SKILL_NAME,
    "setup-lab-orchestrator-service",
    "update-lab-orchestrator-deployment",
)
INSTALLER = ROOT / "scripts" / "manage-codex-skills"
VALIDATOR = ROOT / "scripts" / "validate-codex-skills"


def load_inspector():
    path = SKILL_ROOT / "scripts" / "inspect_deployment.py"
    spec = importlib.util.spec_from_file_location("deployment_inspector", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load deployment inspector")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SkillInstallerTest(unittest.TestCase):
    def run_installer(self, agent_home: Path, *arguments: str) -> subprocess.CompletedProcess:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = str(agent_home)
        return subprocess.run(
            [str(INSTALLER), *arguments],
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_lists_installs_and_reports_idempotent_repo_link(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent_home = Path(directory) / "agent-home"
            listed = self.run_installer(agent_home, "list")
            missing = self.run_installer(agent_home, "status", SKILL_NAME)
            installed = self.run_installer(agent_home, "install", SKILL_NAME)
            repeated = self.run_installer(agent_home, "install", SKILL_NAME)
            status = self.run_installer(agent_home, "status", SKILL_NAME)
            destination = agent_home / "skills" / SKILL_NAME

            self.assertEqual(listed.returncode, 0)
            self.assertEqual(listed.stdout.splitlines(), list(SKILL_NAMES))
            self.assertEqual(missing.returncode, 0)
            self.assertIn("missing", missing.stdout)
            self.assertEqual(installed.returncode, 0)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(destination.resolve(), SKILL_ROOT.resolve())
            self.assertEqual(repeated.returncode, 0)
            self.assertIn("already linked", repeated.stdout)
            self.assertEqual(status.returncode, 0)
            self.assertIn("linked", status.stdout)

    def test_installs_every_catalog_skill_into_temporary_home(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent_home = Path(directory) / "agent-home"
            installed = self.run_installer(agent_home, "install", "all")
            status = self.run_installer(agent_home, "status", "all")

            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertEqual(status.returncode, 0, status.stderr)
            for skill_name in SKILL_NAMES:
                with self.subTest(skill_name=skill_name):
                    destination = agent_home / "skills" / skill_name
                    self.assertTrue(destination.is_symlink())
                    self.assertEqual(
                        destination.resolve(),
                        (ROOT / "skills" / skill_name).resolve(),
                    )
                    self.assertIn(f"linked    {skill_name}", status.stdout)

    def test_refuses_to_replace_unmanaged_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            agent_home = Path(directory) / "agent-home"
            destination = agent_home / "skills" / SKILL_NAME
            destination.mkdir(parents=True)
            marker = destination / "keep.txt"
            marker.write_text("unmanaged\n", encoding="utf-8")

            result = self.run_installer(agent_home, "install", SKILL_NAME)

            self.assertEqual(result.returncode, 1)
            self.assertIn("refusing to replace", result.stderr)
            self.assertIn("diff -ru", result.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "unmanaged\n")

    def test_rejects_relative_agent_home(self) -> None:
        environment = os.environ.copy()
        environment["CODEX_HOME"] = "relative-agent-home"
        result = subprocess.run(
            [str(INSTALLER), "status", SKILL_NAME],
            cwd=ROOT,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be an absolute path", result.stderr)

    def test_refuses_foreign_and_broken_links(self) -> None:
        for target in ("foreign-skill", "missing-skill"):
            with (
                self.subTest(target=target),
                tempfile.TemporaryDirectory() as directory,
            ):
                agent_home = Path(directory) / "agent-home"
                destination = agent_home / "skills" / SKILL_NAME
                destination.parent.mkdir(parents=True)
                target_path = Path(directory) / target
                if target == "foreign-skill":
                    target_path.mkdir()
                destination.symlink_to(target_path, target_is_directory=True)

                result = self.run_installer(agent_home, "install", SKILL_NAME)

                self.assertEqual(result.returncode, 1)
                self.assertIn("refusing to replace", result.stderr)
                self.assertTrue(destination.is_symlink())
                self.assertEqual(os.readlink(destination), str(target_path))

    def test_repository_validator_accepts_skill(self) -> None:
        result = subprocess.run(
            [str(VALIDATOR)],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for skill_name in SKILL_NAMES:
            self.assertIn(f"OK   {skill_name}", result.stdout)


class DeploymentInspectorTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.inspector = load_inspector()

    def arguments(self, *, require_idle: bool = False) -> argparse.Namespace:
        return argparse.Namespace(
            unit="miner-orchestrator.service",
            health_url="http://127.0.0.1:8765/api/v1/health",
            orchestrator=None,
            config=None,
            timeout=10.0,
            require_idle=require_idle,
        )

    def test_reports_healthy_idle_service_safe_to_restart(self) -> None:
        service = {
            "LoadState": "loaded",
            "ActiveState": "active",
            "SubState": "running",
            "FragmentPath": "/example/miner-orchestrator.service",
            "ExecMainStatus": "0",
        }
        health = {
            "status": "ok",
            "config_revision": "a" * 64,
            "queued_assignments": 2,
            "running_assignments": 0,
        }
        with (
            mock.patch.object(self.inspector, "inspect_unit", return_value=service),
            mock.patch.object(self.inspector, "inspect_health", return_value=health),
        ):
            report, successful = self.inspector.inspect(
                self.arguments(require_idle=True)
            )
        self.assertTrue(successful)
        self.assertTrue(report["safe_to_restart"])
        self.assertEqual(report["issues"], [])

    def test_running_assignment_is_healthy_but_not_idle(self) -> None:
        service = {"LoadState": "loaded", "ActiveState": "active"}
        health = {
            "status": "ok",
            "config_revision": "b" * 64,
            "queued_assignments": 0,
            "running_assignments": 1,
        }
        with (
            mock.patch.object(self.inspector, "inspect_unit", return_value=service),
            mock.patch.object(self.inspector, "inspect_health", return_value=health),
        ):
            report, successful = self.inspector.inspect(self.arguments())
            idle_report, idle_successful = self.inspector.inspect(
                self.arguments(require_idle=True)
            )
        self.assertTrue(successful)
        self.assertFalse(report["safe_to_restart"])
        self.assertFalse(idle_successful)
        self.assertIn("not observed idle", " ".join(idle_report["issues"]))

    def test_central_service_must_be_paused_and_have_no_active_lease(self) -> None:
        service = {"LoadState": "loaded", "ActiveState": "active"}
        base_health = {
            "status": "ok",
            "config_revision": "c" * 64,
            "queued_assignments": 0,
            "running_assignments": 0,
        }
        for paused, active_leases, expected in (
            (False, 0, False),
            (True, 1, False),
            (True, 0, True),
        ):
            with self.subTest(paused=paused, active_leases=active_leases):
                health = {
                    **base_health,
                    "central": {
                        "paused": paused,
                        "active_leases": active_leases,
                        "pending_executions": 1,
                        "pending_outbox": 0,
                    },
                }
                with (
                    mock.patch.object(self.inspector, "inspect_unit", return_value=service),
                    mock.patch.object(self.inspector, "inspect_health", return_value=health),
                ):
                    report, successful = self.inspector.inspect(
                        self.arguments(require_idle=True)
                    )
                self.assertEqual(report["safe_to_restart"], expected)
                self.assertEqual(successful, expected)

    def test_health_reader_rejects_credentials_and_oversized_body(self) -> None:
        with self.assertRaisesRegex(self.inspector.InspectionError, "credentials"):
            self.inspector.inspect_health(
                "http://user:password@127.0.0.1:8765/api/v1/health", 10
            )

        class Response:
            headers: dict[str, str] = {}

            def __enter__(self):
                return self

            def __exit__(self, *unused):
                return False

            def read(self, size: int) -> bytes:
                return b"x" * size

        with mock.patch.object(self.inspector, "urlopen", return_value=Response()):
            with self.assertRaisesRegex(self.inspector.InspectionError, "exceeds"):
                self.inspector.inspect_health(
                    "http://127.0.0.1:8765/api/v1/health", 10
                )

    def test_config_validation_requires_one_digest(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout=json.dumps({"ok": True}))
        with mock.patch.object(
            self.inspector.subprocess,
            "run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(self.inspector.InspectionError, "SHA-256"):
                self.inspector.validate_config(Path("orchestrator"), Path("config"), 10)


class SystemdTemplateTest(unittest.TestCase):
    def test_template_preserves_service_and_worker_safety_boundaries(self) -> None:
        unit = (
            SKILL_ROOT / "assets" / "miner-orchestrator.service"
        ).read_text(encoding="utf-8")
        self.assertIn("ExecStartPre=", unit)
        self.assertIn(" validate", unit)
        self.assertIn("ExecStart=", unit)
        self.assertIn(" serve", unit)
        self.assertIn("TimeoutStopSec=infinity", unit)
        self.assertIn("ProtectSystem=strict", unit)
        self.assertIn("ProtectHome=read-only", unit)
        self.assertIn("NoNewPrivileges=true", unit)
        self.assertNotIn("ProtectKernelModules=", unit)
        self.assertIn(
            "ReadOnlyPaths=-%h/.config/mining-qa-lab/orchestrator.env", unit
        )
        self.assertIn(".local/lib/mining-qa-testcode", unit)
        self.assertNotIn("PrivateDevices=true", unit)
        self.assertNotRegex(unit, r"/(?:home|Users)/[^/%\s]+")


class DeploymentDocumentationTest(unittest.TestCase):
    def test_human_and_agent_workflows_share_safety_contract(self) -> None:
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        reference = (SKILL_ROOT / "references" / "deployment-contract.md").read_text(
            encoding="utf-8"
        )
        human = (ROOT / "docs" / "ORCHESTRATOR_DEPLOYMENT.md").read_text(
            encoding="utf-8"
        )

        for text in (skill, reference, human):
            normalized = " ".join(text.split())
            self.assertIn("prepared", normalized)
            self.assertIn("deferred", normalized)
            self.assertIn("drain", normalized)
            self.assertIn("database", normalized.lower())
        self.assertIn("RELEASE_PROVENANCE", human)
        self.assertIn("full commit SHA, and Git tree SHA", reference)


if __name__ == "__main__":
    unittest.main()
