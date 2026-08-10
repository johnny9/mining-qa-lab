from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mining_qa_lab.testcode import (
    CommandResult,
    HostCommandRunner,
    TestcodeInstallError,
    TestcodeInstaller,
)


class FakeCommands:
    def __init__(
        self,
        root: Path,
        *,
        sha: str = "a" * 40,
        origin: str = "git@github.com:johnny9/mining-qa-testcode.git",
        dirty: str = "",
        import_path: Path | None = None,
    ) -> None:
        self.root = root
        self.sha = sha
        self.origin = origin
        self.dirty = dirty
        self.import_path = import_path
        self.has_checkout = False
        self.has_venv = False
        self.installed_sha = sha
        self.calls: list[tuple[dict, list[str], float, object, bool]] = []

    def run(self, host, command, *, timeout, cwd=None, check=True):
        self.calls.append((dict(host), list(command), timeout, cwd, check))
        output = ""
        returncode = 0
        if command[:3] == ["git", "ls-remote", "--exit-code"]:
            ref = command[-1]
            output = f"{self.sha}\t{ref}\n"
        elif command[-3:] == ["remote", "get-url", "origin"]:
            if self.has_checkout:
                output = self.origin + "\n"
            else:
                returncode = 2
        elif command[:2] == ["git", "clone"]:
            self.has_checkout = True
        elif "status" in command:
            output = self.dirty
        elif "fetch" in command:
            self.installed_sha = command[-1].split(":", 1)[0]
        elif "rev-parse" in command:
            output = self.installed_sha + "\n"
        elif command[:2] == ["test", "-x"]:
            returncode = 0 if self.has_venv else 1
        elif command[1:3] == ["-m", "venv"]:
            self.has_venv = True
        elif command[-2:] == ["--editable", str(self.root / "checkout")]:
            output = "installed\n"
        elif "import miner_testcode" in command[-1]:
            import_path = self.import_path or (
                self.root / "checkout" / "src" / "miner_testcode" / "__init__.py"
            )
            output = str(import_path) + "\n"
        result = CommandResult(returncode, output)
        if check and returncode != 0:
            raise AssertionError(f"unexpected checked failure: {command}")
        return result


def configuration(root: Path) -> tuple[dict, dict, dict]:
    policy = {
        "enabled": True,
        "repository": "johnny9/mining-qa-testcode",
        "ref": "main",
        "install_timeout": 120,
    }
    host = {
        "transport": "local",
        "testcode": {
            "checkout": str(root / "checkout"),
            "venv": str(root / "venv"),
            "python": "python3",
        },
    }
    config = {"testcode": policy}
    run = {"id": "gate-run-1"}
    return config, host, run


class TestcodeInstallerTest(unittest.TestCase):
    def test_resolves_once_and_reinstalls_pinned_sha_for_each_assignment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            commands = FakeCommands(root)
            installer = TestcodeInstaller(commands)  # type: ignore[arg-type]
            config, host, run = configuration(root)

            first = installer.ensure(run, "local", host, config, root / "state")
            commands.sha = "b" * 40
            second = installer.ensure(run, "local", host, config, root / "state")

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            self.assertEqual(first.commit_sha, "a" * 40)
            self.assertEqual(second.commit_sha, "a" * 40)
            latest_calls = [
                command
                for _, command, _, _, _ in commands.calls
                if command[:3] == ["git", "ls-remote", "--exit-code"]
            ]
            pip_calls = [
                command
                for _, command, _, _, _ in commands.calls
                if "pip" in command and "--editable" in command
            ]
            self.assertEqual(len(latest_calls), 1)
            self.assertEqual(len(pip_calls), 2)
            marker = root / "state" / "testcode" / "gate-run-1" / "local.json"
            self.assertTrue(marker.is_file())

    def test_rejects_wrong_origin_and_tracked_modifications(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, host, run = configuration(root)

            wrong = FakeCommands(root, origin="https://github.com/other/project.git")
            wrong.has_checkout = True
            with self.assertRaisesRegex(TestcodeInstallError, "origin does not match"):
                TestcodeInstaller(wrong).ensure(  # type: ignore[arg-type]
                    run, "local", host, config, root / "wrong-state"
                )

            dirty = FakeCommands(root, dirty=" M src/miner_testcode/runner.py\n")
            dirty.has_checkout = True
            with self.assertRaisesRegex(TestcodeInstallError, "tracked modifications"):
                TestcodeInstaller(dirty).ensure(  # type: ignore[arg-type]
                    run, "local", host, config, root / "dirty-state"
                )

    def test_rejects_service_venv_and_import_outside_checkout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config, host, run = configuration(root)
            host["testcode"]["venv"] = sys.prefix
            with self.assertRaisesRegex(TestcodeInstallError, "active orchestrator"):
                TestcodeInstaller(FakeCommands(root)).ensure(  # type: ignore[arg-type]
                    run, "local", host, config, root / "service-state"
                )

            config, host, run = configuration(root)
            outside = FakeCommands(root, import_path=root / "other" / "__init__.py")
            with self.assertRaisesRegex(TestcodeInstallError, "outside its checkout"):
                TestcodeInstaller(outside).ensure(  # type: ignore[arg-type]
                    run, "local", host, config, root / "import-state"
                )
            self.assertFalse(
                (root / "import-state" / "testcode" / "gate-run-1" / "local.json").exists()
            )

    def test_rejects_corrupt_marker_before_resolving_or_installing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "state" / "testcode" / "gate-run-1" / "local.json"
            marker.parent.mkdir(parents=True)
            marker.write_text('{"commit_sha":"not-a-sha"}\n', encoding="utf-8")
            commands = FakeCommands(root)
            config, host, run = configuration(root)

            with self.assertRaisesRegex(TestcodeInstallError, "does not match"):
                TestcodeInstaller(commands).ensure(  # type: ignore[arg-type]
                    run, "local", host, config, root / "state"
                )
            self.assertEqual(commands.calls, [])


class HostCommandRunnerTest(unittest.TestCase):
    def test_quotes_remote_command_and_disables_agent_forwarding(self) -> None:
        completed = subprocess.CompletedProcess([], 0, stdout="ok\n")
        with mock.patch(
            "mining_qa_lab.testcode.subprocess.run",
            return_value=completed,
        ) as run:
            result = HostCommandRunner().run(
                {"transport": "ssh", "ssh_target": "mining-lab"},
                ["python3", "-c", "print('two words')"],
                timeout=30,
                cwd="/var/lib/test code",
            )

        invocation = run.call_args.args[0]
        self.assertEqual(invocation[:4], ["ssh", "-o", "ForwardAgent=no", "mining-lab"])
        self.assertIn("cd '/var/lib/test code' &&", invocation[4])
        self.assertIn("'print('\"'\"'two words'\"'\"')'", invocation[4])
        self.assertEqual(result.output, "ok\n")


if __name__ == "__main__":
    unittest.main()
