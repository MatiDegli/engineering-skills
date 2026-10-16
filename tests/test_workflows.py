"""Exercise workflow discovery and download refusal without running fetched code."""

import os
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.validate_repo import ROOT


@unittest.skipUnless(
    platform.system() == "Linux" and platform.machine() == "x86_64",
    "The workflow runner targets Linux x86_64, including WSL2.",
)
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="engineering-skills-workflow-tests-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        scripts = self.root / "scripts"
        scripts.mkdir()
        self.runner = scripts / "check_workflows.sh"
        self.runner.write_bytes((ROOT / "tools/check_workflows.sh").read_bytes())
        self.workflows = self.root / ".github/workflows"
        self.workflows.mkdir(parents=True)
        self.downloads = self.root / "downloads"
        self.downloads.mkdir()
        fake_bin = self.root / "fake-bin"
        fake_bin.mkdir()
        curl = fake_bin / "curl"
        curl.write_text(
            '#!/bin/sh\nprintf called > "$FAKE_DOWNLOAD_LOG"\n'
            'while [ "$#" -gt 0 ]; do\n'
            '  if [ "$1" = --output ]; then\n'
            '    printf "corrupted archive" > "$2"\n'
            "    exit 0\n  fi\n  shift\ndone\nexit 1\n"
        )
        curl.chmod(0o700)
        self.environment = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "TMPDIR": str(self.downloads),
            "FAKE_DOWNLOAD_LOG": str(self.root / "downloaded"),
        }

    def run_check(self):
        return subprocess.run(
            ["bash", str(self.runner)],
            cwd=self.root.parent,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_missing_workflows_fail_before_download(self):
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("No workflows found", result.stderr)
        self.assertFalse((self.root / "downloaded").exists())

    def test_linked_workflow_fails_before_download(self):
        outside = self.root / "outside.yml"
        outside.write_text("name: outside\n")
        (self.workflows / "new.yaml").symlink_to(outside)
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected a regular workflow", result.stderr)
        self.assertFalse((self.root / "downloaded").exists())

    def test_untracked_yaml_is_discovered_and_bad_download_is_never_extracted(self):
        candidate = self.workflows / "new.yaml"
        candidate.write_text("name: kept\n")
        result = self.run_check()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Checksum mismatch", result.stderr)
        self.assertTrue((self.root / "downloaded").exists())
        self.assertEqual(candidate.read_text(), "name: kept\n")
        self.assertEqual(list(self.downloads.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
