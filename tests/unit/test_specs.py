from __future__ import annotations

import re
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "specs"
ALLOWED_LIFECYCLES = {
    "proposed",
    "implementing",
    "supported",
    "deprecated",
    "retired",
}
FEATURE_FILES = {"SPEC.md", "intent.md", "design.md", "acceptance.md", "risks.md"}
REQUIRED_HEADINGS = {
    "intent.md": {
        "Problem",
        "Why it matters",
        "Stakeholders",
        "Desired outcome",
        "Primary flow",
        "Alternate and failure flows",
        "Non-goals",
    },
    "design.md": {
        "Components and responsibilities",
        "Interfaces and contracts",
        "CLI",
        "Configuration",
        "Environment",
        "Python API",
        "HTTP or external protocols",
        "Files, artifacts, payloads, and persistent state",
        "Contract constraints",
        "Required invariants",
        "Forbidden behavior",
        "Data and state",
        "Control and data flow",
        "Failure and recovery",
        "Compatibility and migration",
        "Resource and operational constraints",
        "Relationships to other feature slices",
        "Verification approach",
    },
    "acceptance.md": {
        "Functional behavior",
        "Interfaces and compatibility",
        "Quality attributes",
        "Verification evidence",
        "Acceptance rule",
    },
    "risks.md": {
        "Scope",
        "In",
        "Out",
        "Assumptions",
        "Open questions",
        "Failure modes",
        "Security, privacy, and safety",
        "Performance and resource risks",
        "Rollout and rollback",
    },
}


def feature_specs() -> list[Path]:
    return sorted(
        path
        for path in SPECS.rglob("SPEC.md")
        if "_template" not in path.parts
    )


class SpecificationIntegrityTest(unittest.TestCase):
    maxDiff = None

    def test_index_lists_every_feature_once_and_matches_lifecycle(self) -> None:
        index = (SPECS / "INDEX.md").read_text(encoding="utf-8")
        entries = re.findall(
            r"^\| `([^`]+)` \| [^|]+ \| `?([a-z]+)`? \| "
            r"\[SPEC\.md\]\(([^)]+/SPEC\.md)\) \|",
            index,
            flags=re.MULTILINE,
        )
        indexed = [SPECS / target for _, _, target in entries]
        discovered = feature_specs()

        self.assertEqual(
            Counter(indexed),
            Counter(discovered),
            "specs/INDEX.md must list every non-template feature SPEC.md exactly once",
        )
        self.assertTrue(all(count == 1 for count in Counter(indexed).values()))

        for area, lifecycle, target in entries:
            spec_path = SPECS / target
            self.assertEqual(area, spec_path.relative_to(SPECS).parts[0])
            text = spec_path.read_text(encoding="utf-8")
            match = re.search(r"^- \*\*Lifecycle:\*\* ([a-z]+)$", text, re.MULTILINE)
            self.assertIsNotNone(match, f"missing lifecycle in {spec_path}")
            self.assertEqual(lifecycle, match.group(1), spec_path)
            self.assertIn(lifecycle, ALLOWED_LIFECYCLES, spec_path)

    def test_feature_documents_have_required_metadata_and_sections(self) -> None:
        spec_ids: list[str] = []
        for spec_path in feature_specs():
            directory = spec_path.parent
            missing = sorted(name for name in FEATURE_FILES if not (directory / name).is_file())
            self.assertFalse(missing, f"{directory} is missing {missing}")

            spec = spec_path.read_text(encoding="utf-8")
            self.assertRegex(spec, r"(?m)^# \S")
            self.assertRegex(spec, r"(?m)^- \*\*Owner:\*\* \S")
            self.assertRegex(spec, r"(?m)^- \*\*Last reconciled:\*\* \d{4}-\d{2}-\d{2}$")
            id_match = re.search(r"(?m)^- \*\*Spec ID:\*\* ([A-Z][A-Z0-9-]+)$", spec)
            self.assertIsNotNone(id_match, f"missing Spec ID in {spec_path}")
            spec_id = id_match.group(1)
            spec_ids.append(spec_id)
            self.assertIn("## Changelog", spec)
            self.assertRegex(spec.split("## Changelog", 1)[1], r"\d{4}-\d{2}-\d{2}")
            for companion in FEATURE_FILES - {"SPEC.md"}:
                self.assertIn(f"({companion})", spec, f"{spec_path} must link {companion}")

            for name, expected in REQUIRED_HEADINGS.items():
                text = (directory / name).read_text(encoding="utf-8")
                headings = set(re.findall(r"^#{2,4} (.+?)\s*$", text, re.MULTILINE))
                self.assertFalse(expected - headings, f"{directory / name} missing {sorted(expected - headings)}")

            acceptance = (directory / "acceptance.md").read_text(encoding="utf-8")
            criteria = re.findall(r"\*\*([A-Z][A-Z0-9-]+-AC-\d{2,}):\*\*", acceptance)
            self.assertTrue(criteria, f"no stable acceptance IDs in {directory / 'acceptance.md'}")
            self.assertTrue(
                all(item.startswith(f"{spec_id}-AC-") for item in criteria),
                f"acceptance IDs do not match {spec_id} in {directory}",
            )
            self.assertEqual(len(criteria), len(set(criteria)), f"duplicate acceptance ID in {directory}")

        self.assertEqual(len(spec_ids), len(set(spec_ids)), "feature Spec IDs must be unique")

    def test_relative_markdown_links_resolve(self) -> None:
        failures: list[str] = []
        for document in sorted(SPECS.rglob("*.md")):
            text = document.read_text(encoding="utf-8")
            for raw_target in re.findall(r"\[[^]]*\]\(([^)]+)\)", text):
                target = raw_target.strip().strip("<>").split("#", 1)[0]
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue
                if "{{" in target:
                    continue
                resolved = (document.parent / target).resolve()
                if not resolved.exists():
                    failures.append(f"{document.relative_to(ROOT)} -> {raw_target}")
        self.assertFalse(failures, "unresolved Markdown links:\n" + "\n".join(failures))

    def test_design_implementation_pointers_exist(self) -> None:
        failures: list[str] = []
        for design in sorted(SPECS.glob("*/*/design.md")):
            text = design.read_text(encoding="utf-8")
            for token in re.findall(r"`((?:src|tests|configs)/[^`\s]+)`", text):
                path_text = re.sub(r"(?<=\.py):.+$", "", token).rstrip(".,")
                if not (ROOT / path_text).exists():
                    failures.append(f"{design.relative_to(ROOT)} -> {token}")
        self.assertFalse(failures, "missing implementation pointers:\n" + "\n".join(failures))

    def test_non_template_documents_have_no_template_placeholders(self) -> None:
        failures: list[str] = []
        for document in sorted(SPECS.rglob("*.md")):
            if "_template" in document.parts or document == SPECS / "reviews" / "TEMPLATE.md":
                continue
            if re.search(r"\{\{[A-Z0-9_]+\}\}", document.read_text(encoding="utf-8")):
                failures.append(str(document.relative_to(ROOT)))
        self.assertFalse(failures, "unresolved template placeholders: " + ", ".join(failures))


if __name__ == "__main__":
    unittest.main()
