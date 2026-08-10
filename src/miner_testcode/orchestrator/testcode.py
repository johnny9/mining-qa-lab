from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

from ..errors import ConfigError

_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SCP_GITHUB = re.compile(
    r"^(?:[^@]+@)?github\.com:(?P<repository>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?:\.git)?$"
)
_MAX_DIAGNOSTIC_CHARS = 64 * 1024
_MAX_MARKER_BYTES = 16 * 1024


class TestcodeInstallError(ConfigError):
    pass


@dataclass(frozen=True, slots=True)
class CommandResult:
    returncode: int
    output: str


class HostCommandRunner:
    """Run one bounded shell-free local command or safely quoted SSH command."""

    def run(
        self,
        host: Mapping[str, Any],
        command: list[str],
        *,
        timeout: float,
        cwd: str | Path | None = None,
        check: bool = True,
    ) -> CommandResult:
        if not command:
            raise TestcodeInstallError("testcode install command must not be empty")
        transport = str(host.get("transport") or "local")
        invocation = list(command)
        local_cwd = str(cwd) if cwd is not None else None
        if transport == "ssh":
            remote = shlex.join(command)
            if cwd is not None:
                remote = f"cd {shlex.quote(str(cwd))} && {remote}"
            invocation = [
                "ssh",
                "-o",
                "ForwardAgent=no",
                str(host["ssh_target"]),
                remote,
            ]
            local_cwd = None
        try:
            completed = subprocess.run(
                invocation,
                cwd=local_cwd,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise TestcodeInstallError(
                f"testcode command failed to start or timed out: {type(exc).__name__}: {exc}"
            ) from exc
        output = (completed.stdout or "")[-_MAX_DIAGNOSTIC_CHARS:]
        if check and completed.returncode != 0:
            detail = output.strip() or f"exit {completed.returncode}"
            raise TestcodeInstallError(
                f"testcode command {shlex.join(command[:3])} failed: "
                f"{detail[-4000:]}"
            )
        return CommandResult(completed.returncode, output)


@dataclass(frozen=True, slots=True)
class TestcodeInstallation:
    repository: str
    ref: str
    commit_sha: str
    checkout: Path
    venv: Path
    executable: Path
    log: str

    @property
    def metadata(self) -> dict[str, str]:
        return {
            "repository": self.repository,
            "ref": self.ref,
            "commit_sha": self.commit_sha,
        }


def _github_repository(remote: str) -> str:
    value = remote.strip()
    match = _SCP_GITHUB.fullmatch(value)
    if match:
        return match.group("repository")
    parsed = urlsplit(value)
    if parsed.hostname != "github.com":
        raise TestcodeInstallError("managed testcode origin must be hosted on github.com")
    repository = parsed.path.strip("/")
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not _REPOSITORY.fullmatch(repository):
        raise TestcodeInstallError(
            "managed testcode origin must have GitHub owner/repository form"
        )
    return repository


def _write_marker(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)


class TestcodeInstaller:
    def __init__(self, commands: HostCommandRunner | None = None) -> None:
        self.commands = commands or HostCommandRunner()
        self._lock = threading.Lock()

    @staticmethod
    def _clone_url(repository: str) -> str:
        return f"https://github.com/{repository}.git"

    def _latest_sha(self, repository: str, ref: str, timeout: float) -> str:
        result = self.commands.run(
            {"transport": "local"},
            [
                "git",
                "ls-remote",
                "--exit-code",
                self._clone_url(repository),
                f"refs/heads/{ref}",
            ],
            timeout=timeout,
        )
        matches = []
        for line in result.output.splitlines():
            fields = line.split()
            if len(fields) == 2 and fields[1] == f"refs/heads/{ref}":
                matches.append(fields[0].lower())
        if len(matches) != 1 or not _SHA.fullmatch(matches[0]):
            raise TestcodeInstallError(
                f"could not resolve one exact testcode SHA for {repository}@{ref}"
            )
        return matches[0]

    @staticmethod
    def _marker_sha(path: Path, repository: str, ref: str) -> str | None:
        if not path.exists():
            return None
        if path.stat().st_size > _MAX_MARKER_BYTES:
            raise TestcodeInstallError("testcode install marker exceeds 16 KiB")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TestcodeInstallError(f"invalid testcode install marker: {exc}") from exc
        if not isinstance(payload, dict):
            raise TestcodeInstallError("testcode install marker must be an object")
        sha = payload.get("commit_sha")
        if (
            payload.get("schema_version") != 1
            or payload.get("repository") != repository
            or payload.get("ref") != ref
            or not isinstance(sha, str)
            or not _SHA.fullmatch(sha)
        ):
            raise TestcodeInstallError(
                "testcode install marker does not match the captured configuration"
            )
        return sha

    def _install(
        self,
        host: Mapping[str, Any],
        *,
        repository: str,
        sha: str,
        checkout: Path,
        venv: Path,
        python: str,
        timeout: float,
    ) -> str:
        active_service_venv = Path(sys.prefix).resolve()
        if host.get("transport", "local") == "local" and venv.resolve() == active_service_venv:
            raise TestcodeInstallError(
                "managed runner venv must not be the active orchestrator environment"
            )
        logs: list[str] = [f"testcode: installing {repository}@{sha}"]

        def run(command: list[str], *, check: bool = True) -> CommandResult:
            result = self.commands.run(host, command, timeout=timeout, check=check)
            if result.output.strip():
                logs.append(result.output.strip())
            return result

        run(["mkdir", "-p", str(checkout.parent), str(venv.parent)])
        origin = run(
            ["git", "-C", str(checkout), "remote", "get-url", "origin"],
            check=False,
        )
        if origin.returncode != 0:
            run(["git", "clone", "--no-checkout", self._clone_url(repository), str(checkout)])
            origin = run(["git", "-C", str(checkout), "remote", "get-url", "origin"])
        if _github_repository(origin.output) != repository:
            raise TestcodeInstallError(
                "managed testcode checkout origin does not match testcode.repository"
            )
        dirty = run(
            ["git", "-C", str(checkout), "status", "--porcelain", "--untracked-files=no"]
        )
        if dirty.output.strip():
            raise TestcodeInstallError(
                "managed testcode checkout has tracked modifications; refusing to overwrite"
            )
        installed_ref = "refs/remotes/origin/orchestrator-installed"
        run(
            [
                "git",
                "-C",
                str(checkout),
                "fetch",
                "--force",
                "--depth",
                "1",
                "origin",
                f"{sha}:{installed_ref}",
            ]
        )
        fetched = run(["git", "-C", str(checkout), "rev-parse", installed_ref])
        fetched_sha = fetched.output.strip().lower()
        if fetched_sha != sha:
            raise TestcodeInstallError(
                f"managed testcode fetch resolved {fetched_sha or 'no SHA'} instead of {sha}"
            )
        run(["git", "-C", str(checkout), "checkout", "--detach", sha])
        checked_out = run(["git", "-C", str(checkout), "rev-parse", "HEAD"])
        if checked_out.output.strip().lower() != sha:
            raise TestcodeInstallError(
                "managed testcode checkout did not retain the pinned commit"
            )

        venv_python = venv / "bin" / "python"
        present = run(["test", "-x", str(venv_python)], check=False)
        if present.returncode != 0:
            run([python, "-m", "venv", str(venv)])
        run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-input",
                "--upgrade",
                "--editable",
                str(checkout),
            ]
        )
        imported = run(
            [
                str(venv_python),
                "-c",
                (
                    "from pathlib import Path; import miner_testcode; "
                    "print(Path(miner_testcode.__file__).resolve())"
                ),
            ]
        )
        lines = [line.strip() for line in imported.output.splitlines() if line.strip()]
        expected = (checkout / "src" / "miner_testcode" / "__init__.py").as_posix()
        if not lines or Path(lines[-1]).as_posix() != expected:
            raise TestcodeInstallError(
                "managed runner environment imported testcode outside its checkout"
            )
        run(["test", "-x", str(venv / "bin" / "miner-test")])
        return ("\n".join(logs) + "\n")[-_MAX_DIAGNOSTIC_CHARS:]

    def ensure(
        self,
        run: Mapping[str, Any],
        host_id: str,
        host: Mapping[str, Any],
        config: Mapping[str, Any],
        state_dir: Path,
    ) -> TestcodeInstallation | None:
        policy = config.get("testcode", {})
        if not policy.get("enabled", False):
            return None
        repository = str(policy["repository"])
        ref = str(policy["ref"])
        timeout = float(policy["install_timeout"])
        host_policy = host["testcode"]
        checkout = Path(str(host_policy["checkout"]))
        venv = Path(str(host_policy["venv"]))
        python = str(host_policy.get("python") or "python3")
        marker = state_dir / "testcode" / str(run["id"]) / f"{host_id}.json"

        with self._lock:
            sha = self._marker_sha(marker, repository, ref)
            if sha is None:
                sha = self._latest_sha(repository, ref, timeout)
            log = self._install(
                host,
                repository=repository,
                sha=sha,
                checkout=checkout,
                venv=venv,
                python=python,
                timeout=timeout,
            )
            if not marker.exists():
                _write_marker(
                    marker,
                    {
                        "schema_version": 1,
                        "repository": repository,
                        "ref": ref,
                        "commit_sha": sha,
                        "host": host_id,
                    },
                )
        return TestcodeInstallation(
            repository=repository,
            ref=ref,
            commit_sha=sha,
            checkout=checkout,
            venv=venv,
            executable=venv / "bin" / "miner-test",
            log=log,
        )
