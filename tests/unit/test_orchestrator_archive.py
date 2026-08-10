from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mining_qa_lab.archive import ArtifactArchiver
from mining_qa_lab.errors import ConfigError


def archive_fixture(root: Path) -> tuple[dict[str, object], bytes, bytes]:
    artifact = b"sanitized runner output\n"
    manifest = json.dumps(
        {
            "version": 1,
            "run_id": "runner-run",
            "artifacts": [
                {
                    "path": "logs/runner.log",
                    "size_bytes": len(artifact),
                    "sha256": hashlib.sha256(artifact).hexdigest(),
                    "media_type": "text/plain",
                }
            ],
        },
        sort_keys=True,
    ).encode()
    pointer = {
        "artifact_root": str(root),
        "artifact_manifest": {
            "path": "orchestration-artifacts.json",
            "size_bytes": len(manifest),
            "sha256": hashlib.sha256(manifest).hexdigest(),
        },
    }
    return pointer, manifest, artifact


class ArtifactArchiverTest(unittest.TestCase):
    def test_archives_and_verifies_local_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "runner-artifacts"
            (source / "logs").mkdir(parents=True)
            pointer, manifest, artifact = archive_fixture(source)
            (source / "orchestration-artifacts.json").write_bytes(manifest)
            (source / "logs" / "runner.log").write_bytes(artifact)

            records = ArtifactArchiver().archive(
                pointer,
                gate_run_id="gate-run",
                assignment_id="assignment",
                attempt=1,
                host={"transport": "local"},
                state_dir=base / "state",
            )

            archived = Path(records[0]["storage_path"])
            self.assertEqual(archived.read_bytes(), artifact)
            self.assertEqual(records[0]["relative_path"], "logs/runner.log")
            self.assertEqual(archived.stat().st_mode & 0o777, 0o600)

    def test_rejects_tampered_artifact_without_installing_archive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "runner-artifacts"
            (source / "logs").mkdir(parents=True)
            pointer, manifest, _ = archive_fixture(source)
            (source / "orchestration-artifacts.json").write_bytes(manifest)
            (source / "logs" / "runner.log").write_bytes(b"tampered\n")

            with self.assertRaisesRegex(ConfigError, "SHA-256"):
                ArtifactArchiver().archive(
                    pointer,
                    gate_run_id="gate-run",
                    assignment_id="assignment",
                    attempt=1,
                    host={"transport": "local"},
                    state_dir=base / "state",
                )

            self.assertFalse(
                (
                    base
                    / "state"
                    / "archive"
                    / "gate-run"
                    / "assignment"
                    / "attempt-1"
                ).exists()
            )

    def test_rejects_symlinked_local_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "runner-artifacts"
            (source / "logs").mkdir(parents=True)
            pointer, manifest, artifact = archive_fixture(source)
            (source / "orchestration-artifacts.json").write_bytes(manifest)
            target = source / "actual.log"
            target.write_bytes(artifact)
            (source / "logs" / "runner.log").symlink_to(target)

            with self.assertRaisesRegex(ConfigError, "symlink"):
                ArtifactArchiver().archive(
                    pointer,
                    gate_run_id="gate-run",
                    assignment_id="assignment",
                    attempt=1,
                    host={"transport": "local"},
                    state_dir=base / "state",
                )

    def test_retrieves_remote_manifest_and_file_with_bounded_ssh_reads(self) -> None:
        pointer, manifest, artifact = archive_fixture(Path("/remote/run"))

        def run(command, **kwargs):
            self.assertEqual(command[:4], ["ssh", "-o", "ForwardAgent=no", "lab"])
            output = manifest if "orchestration-artifacts.json" in command[4] else artifact
            return mock.Mock(returncode=0, stdout=output, stderr=b"")

        with tempfile.TemporaryDirectory() as directory, mock.patch(
            "mining_qa_lab.archive.subprocess.run", side_effect=run
        ):
            records = ArtifactArchiver().archive(
                pointer,
                gate_run_id="gate-run",
                assignment_id="assignment",
                attempt=1,
                host={"transport": "ssh", "ssh_target": "lab"},
                state_dir=Path(directory),
            )

        self.assertEqual(len(records), 1)
