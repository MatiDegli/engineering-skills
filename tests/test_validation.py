"""Regression checks for broken links, structured data and filename hygiene."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.validate_repo import ROOT, markdown_errors, secret_like, validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="engineering-skills-validation-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()

    def test_links_are_local_portable_and_not_examples(self):
        (self.root / "target file.md").write_text("# Target\n")
        good = (
            "# Heading\n[target](<target file.md>) [encoded](target%20file.md#target) "
            "[web](https://example.com) [heading](#heading)\n"
            "```md\n[example](missing.md)\n```\n"
        )
        path = self.root / "README.md"
        path.write_text(good)
        self.assertEqual(markdown_errors(path, good, self.root), [])
        for target in ("", "missing.md", "../escape.md", "/tmp/file", r"C:\repo\file"):
            with self.subTest(target=target):
                self.assertTrue(markdown_errors(path, f"[x]({target})", self.root))

    def test_heading_fragments_include_unicode_formatting_and_duplicate_collisions(
        self,
    ):
        target = self.root / "guide.md"
        target.write_text(
            "# Quality Ω checks\n## Review\n## Review\n## Review-1\n"
            "## Review\n## API `check_api_size`\n## **Plain** _text_ ###\n",
            encoding="utf-8",
        )
        path = self.root / "README.md"
        for anchor in (
            "quality-%CF%89-checks",
            "review",
            "review-1",
            "review-1-1",
            "review-2",
            "api-check_api_size",
            "plain-text",
        ):
            with self.subTest(anchor=anchor):
                text = f"[section](guide.md#{anchor})\n"
                self.assertEqual(markdown_errors(path, text, self.root), [])
        self.assertTrue(markdown_errors(path, "[x](guide.md#review-3)", self.root))

    def test_fenced_examples_are_not_headings_or_live_links(self):
        text = (
            "# Visible\n````md\n# Hidden\n```\n[x](missing.md)\n```\n````\n"
            "~~~md\n# Also hidden\n[x](missing.md)\n~~~\n"
            "`[example](missing.md)` [real](#visible)\n#\nNot a heading\n"
        )
        path = self.root / "README.md"
        path.write_text(text)
        self.assertEqual(markdown_errors(path, text, self.root), [])
        for anchor in ("hidden", "also-hidden", "not-a-heading"):
            self.assertTrue(markdown_errors(path, text + f"[x](#{anchor})", self.root))

    def test_validator_cli_rejects_missing_same_file_anchor_and_accepts_fix(self):
        tools = self.root / "tools"
        tools.mkdir()
        runner = tools / "validate_repo.py"
        runner.write_bytes((ROOT / "tools/validate_repo.py").read_bytes())
        path = self.root / "README.md"
        for heading, code in (("Old heading", 1), ("New heading", 0)):
            path.write_text(f"# {heading}\n[section](#new-heading)\n")
            result = subprocess.run(
                [sys.executable, str(runner)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertEqual(result.returncode, code, result.stdout + result.stderr)
            if code:
                self.assertIn("missing heading anchor", result.stdout)

    def test_malformed_structures_and_whitespace_fail(self):
        (self.root / "bad.json").write_text("{\n")
        (self.root / "bad.toml").write_text("x = [\n")
        (self.root / "README.md").write_text("trailing \nno final newline")
        (self.root / "windows.txt").write_bytes(b"line\r\n")
        self.assertEqual(len(validate(self.root)), 5)

    def test_dependency_trees_are_pruned(self):
        (self.root / "node_modules").mkdir()
        (self.root / "node_modules/bad.json").write_text("invalid")
        self.assertEqual(validate(self.root), [])

    def test_secret_filenames_include_env_variants_but_allow_examples(self):
        for name in (
            ".env",
            ".env.production",
            ".env.local",
            "id_ed25519",
            "private.key",
        ):
            self.assertTrue(secret_like(Path(name)), name)
        for name in (".env.example", ".env.production.example", "package-lock.json"):
            self.assertFalse(secret_like(Path(name)), name)

    def test_git_includes_force_added_secrets_and_untracked_candidates(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text(".env*\n")
        (self.root / ".env.local").write_text("EXAMPLE=placeholder\n")
        self.assertEqual(validate(self.root), [])
        subprocess.run(["git", "add", "-f", ".env.local"], cwd=self.root, check=True)
        (self.root / "credentials.json").write_text("{}\n")
        errors = validate(self.root)
        self.assertEqual(len(errors), 2)
        self.assertTrue(any(".env.local" in error for error in errors))
        self.assertTrue(any("credentials.json" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
