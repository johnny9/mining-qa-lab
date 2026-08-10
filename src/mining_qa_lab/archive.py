from __future__ import annotations

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .errors import ConfigError


MAX_MANIFEST_BYTES = 256 * 1024
MAX_ARTIFACTS = 512
MAX_ARTIFACT_BYTES = 50 * 1024 * 1024
MAX_ARCHIVE_BYTES = 512 * 1024 * 1024


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str) or not value or len(value) > 512:
        raise ConfigError("artifact manifest path must be a bounded relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigError("artifact manifest path must not escape its run root")
    return path


class ArtifactArchiver:
    @staticmethod
    def _local_read(root: str, relative: PurePosixPath, limit: int) -> bytes:
        configured_root = Path(root).expanduser()
        if not configured_root.is_absolute():
            raise ConfigError("artifact_root must be absolute")
        source_root = configured_root.resolve()
        candidate = source_root.joinpath(*relative.parts)
        current = source_root
        for part in relative.parts:
            current /= part
            if current.is_symlink():
                raise ConfigError(f"artifact path contains a symlink: {relative}")
        source = candidate.resolve()
        if not source.is_relative_to(source_root) or not source.is_file():
            raise ConfigError(f"artifact is outside or missing from run root: {relative}")
        with source.open("rb") as stream:
            return stream.read(limit + 1)

    @staticmethod
    def _ssh_read(
        host: Mapping[str, Any], root: str, relative: PurePosixPath, limit: int
    ) -> bytes:
        root_path = PurePosixPath(root)
        if not root_path.is_absolute():
            raise ConfigError("remote artifact_root must be absolute")
        remote_path = str(root_path.joinpath(relative))
        quoted_root = shlex.quote(str(root_path))
        quoted_path = shlex.quote(remote_path)
        current = root_path
        symlink_checks = []
        for part in relative.parts:
            current /= part
            symlink_checks.append(f"test ! -L {shlex.quote(str(current))}")
        command = (
            " && ".join(symlink_checks)
            + " && "
            + f"root=$(realpath -e -- {quoted_root}) && "
            f"file=$(realpath -e -- {quoted_path}) && "
            'case "$file" in "$root"/*) '
            f'test -f "$file" && head -c {limit + 1} -- "$file";; '
            "*) exit 66;; esac"
        )
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    "ForwardAgent=no",
                    str(host["ssh_target"]),
                    command,
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise ConfigError(f"could not retrieve remote artifact: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr[:1000].decode("utf-8", errors="replace")
            raise ConfigError(f"could not retrieve remote artifact: {detail}")
        return result.stdout

    def _read(
        self,
        host: Mapping[str, Any],
        root: str,
        relative: PurePosixPath,
        limit: int,
    ) -> bytes:
        if host["transport"] == "ssh":
            return self._ssh_read(host, root, relative, limit)
        return self._local_read(root, relative, limit)

    def archive(
        self,
        pointer: Mapping[str, Any],
        *,
        gate_run_id: str,
        assignment_id: str,
        attempt: int,
        host: Mapping[str, Any],
        state_dir: Path,
    ) -> list[dict[str, Any]]:
        descriptor = pointer.get("artifact_manifest")
        if descriptor is None:
            return []
        if not isinstance(descriptor, Mapping):
            raise ConfigError("artifact_manifest must be an object")
        root = pointer.get("artifact_root")
        if not isinstance(root, str) or not root:
            raise ConfigError("artifact archive requires artifact_root")
        manifest_path = _safe_relative_path(descriptor.get("path"))
        if len(manifest_path.parts) != 1:
            raise ConfigError("artifact manifest must be at the run root")
        size = descriptor.get("size_bytes")
        digest = descriptor.get("sha256")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or size < 1
            or size > MAX_MANIFEST_BYTES
            or not isinstance(digest, str)
            or len(digest) != 64
        ):
            raise ConfigError("artifact manifest descriptor is invalid")
        encoded = self._read(host, root, manifest_path, size)
        if len(encoded) != size or _digest(encoded) != digest.lower():
            raise ConfigError("artifact manifest size or SHA-256 did not match")
        try:
            manifest = json.loads(encoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ConfigError(f"artifact manifest is invalid JSON: {exc}") from exc
        if not isinstance(manifest, dict) or manifest.get("version") != 1:
            raise ConfigError("unsupported artifact manifest version")
        if (
            isinstance(pointer.get("run_id"), str)
            and manifest.get("run_id") != pointer["run_id"]
        ):
            raise ConfigError("artifact manifest run_id did not match the result pointer")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) > MAX_ARTIFACTS:
            raise ConfigError("artifact manifest has an invalid file list")

        archive_root = (
            state_dir
            / "archive"
            / gate_run_id
            / assignment_id
            / f"attempt-{attempt}"
        )
        temporary = archive_root.with_name(
            f".{archive_root.name}.{uuid.uuid4().hex}.tmp"
        )
        if archive_root.exists():
            raise ConfigError("artifact archive attempt already exists")
        temporary.mkdir(parents=True, exist_ok=False)
        records: list[dict[str, Any]] = []
        total = 0
        try:
            for item in artifacts:
                if not isinstance(item, Mapping):
                    raise ConfigError("artifact manifest entries must be objects")
                relative = _safe_relative_path(item.get("path"))
                artifact_size = item.get("size_bytes")
                artifact_digest = item.get("sha256")
                media_type = item.get("media_type", "application/octet-stream")
                if (
                    isinstance(artifact_size, bool)
                    or not isinstance(artifact_size, int)
                    or artifact_size < 0
                    or artifact_size > MAX_ARTIFACT_BYTES
                    or not isinstance(artifact_digest, str)
                    or len(artifact_digest) != 64
                    or not isinstance(media_type, str)
                    or not media_type
                    or len(media_type) > 128
                    or "\r" in media_type
                    or "\n" in media_type
                ):
                    raise ConfigError(f"invalid artifact manifest entry: {relative}")
                total += artifact_size
                if total > MAX_ARCHIVE_BYTES:
                    raise ConfigError("artifact archive exceeds the 512 MiB run limit")
                value = self._read(host, root, relative, artifact_size)
                if len(value) != artifact_size or _digest(value) != artifact_digest.lower():
                    raise ConfigError(f"artifact size or SHA-256 did not match: {relative}")
                destination = temporary.joinpath(*relative.parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                descriptor_fd = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                )
                with os.fdopen(descriptor_fd, "wb") as stream:
                    stream.write(value)
                records.append(
                    {
                        "id": str(uuid.uuid4()),
                        "assignment_id": assignment_id,
                        "attempt": attempt,
                        "relative_path": relative.as_posix(),
                        "size_bytes": artifact_size,
                        "sha256": artifact_digest.lower(),
                        "media_type": media_type,
                        "storage_path": "",
                    }
                )
            archive_root.parent.mkdir(parents=True, exist_ok=True)
            os.replace(temporary, archive_root)
            for record in records:
                record["storage_path"] = str(
                    archive_root.joinpath(*PurePosixPath(record["relative_path"]).parts)
                )
            return records
        except Exception:
            shutil.rmtree(temporary, ignore_errors=True)
            raise
