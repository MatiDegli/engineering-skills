"""Regression checks for skill metadata, portable references, and criteria IDs."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.check_skills import ROOT, criteria_ids, validate

SKILL = """---
name: {name}
description: {description}
---

# Example

Read [criteria](references/criteria.md) and [guide](references/guide.md).
"""
CRITERIA = """# Criteria

| ID | Check | Applies when | Guide |
| --- | --- | --- | --- |
| AREA-01 | First check | Always | [guide](guide.md#guide) |
| AREA-02 | Second check | Always | [guide](guide.md#guide) |
"""


class SkillTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="engineering-skills-skills-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.skill = self.root / "skills" / "checking-things"
        (self.skill / "references").mkdir(parents=True)
        self.write_skill()
        (self.skill / "references" / "criteria.md").write_text(CRITERIA)
        (self.skill / "references" / "guide.md").write_text("# Guide\n")

    def write_skill(self, name="checking-things", description="Checks things. Use when asked."):
        (self.skill / "SKILL.md").write_text(SKILL.format(name=name, description=description))

    def test_valid_skill_passes_and_ids_are_read_in_order(self):
        self.assertEqual(validate(self.root), [])
        text = (self.skill / "references" / "criteria.md").read_text()
        self.assertEqual(criteria_ids(text), ["AREA-01", "AREA-02"])

    def test_invalid_names_and_descriptions_fail(self):
        for name, description in (
            ("Checking-Things", "Valid."),
            ("checking--things", "Valid."),
            ("other-name", "Valid."),
            ("x" * 65, "Valid."),
            ("checking-things", ""),
            ("checking-things", "Uses <tags> inside."),
            ("checking-things", "x" * 1025),
        ):
            with self.subTest(name=name[:20], description=description[:20]):
                self.write_skill(name, description)
                self.assertTrue(validate(self.root))

    def test_client_specific_fields_fail(self):
        path = self.skill / "SKILL.md"
        path.write_text(path.read_text().replace("---\n\n", "context: fork\n---\n\n", 1))
        self.assertIn("outside the Agent Skills specification: context", "\n".join(validate(self.root)))

    def test_reserved_words_fail(self):
        reserved = self.root / "skills" / "claude-helper"
        self.skill.rename(reserved)
        self.skill = reserved
        self.write_skill(name="claude-helper")
        self.assertIn("reserved word", "\n".join(validate(self.root)))

    def test_malformed_frontmatter_and_missing_skill_fail(self):
        (self.skill / "SKILL.md").write_text("name: checking-things\n")
        self.assertIn("frontmatter", "\n".join(validate(self.root)))
        (self.skill / "SKILL.md").unlink()
        self.assertIn("missing SKILL.md", "\n".join(validate(self.root)))

    def test_unlinked_reference_and_escaping_link_fail(self):
        (self.skill / "references" / "orphan.md").write_text("# Orphan\n")
        (self.root / "outside.md").write_text("# Outside\n")
        with (self.skill / "references" / "guide.md").open("a") as guide:
            guide.write("[outside](../../../outside.md)\n")
        errors = "\n".join(validate(self.root))
        self.assertIn("orphan.md: not linked from SKILL.md", errors)
        self.assertIn("link leaves the skill directory", errors)

    def test_criteria_ids_must_be_unique_well_formed_and_linked(self):
        path = self.skill / "references" / "criteria.md"
        for row, message in (
            ("| AREA-01 | Repeated | Always | [guide](guide.md) |", "duplicate"),
            ("| AREA-3 | Short | Always | [guide](guide.md) |", "malformed"),
            ("| AREA-03 | No link | Always | guide |", "guide link"),
        ):
            with self.subTest(message=message):
                path.write_text(CRITERIA + row + "\n")
                self.assertIn(message, "\n".join(validate(self.root)))

    def test_cli_rejects_a_bad_skill_and_accepts_the_fix(self):
        (self.root / "tools").mkdir()
        for name in ("validate_repo.py", "check_skills.py"):
            (self.root / "tools" / name).write_bytes((ROOT / "tools" / name).read_bytes())
        for name, code in (("Bad-Name", 1), ("checking-things", 0)):
            self.write_skill(name=name)
            result = subprocess.run(
                [sys.executable, "-m", "tools.check_skills"],
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
