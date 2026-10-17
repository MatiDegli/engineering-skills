"""Check report parsing, scoring outcomes, case consistency, and fixture preparation."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.evals import (
    CASES,
    bad_citations,
    catalog,
    compare,
    finding_rows,
    leaked,
    misplaced_citations,
    prepare,
    priority_actions,
    priority_placement,
    priority_summary,
    report_statuses,
    score,
    verify,
)

REPORT = """## Findings
| ID | Status | Priority | Evidence | Improvement |
| --- | --- | --- | --- | --- |
| CI-02 | `partial` | high | `ci.yml:3` runs `pytest || true` | Pin it |
| SEC-05 | pending-implementation | high | `settings.py:1` | Rotate |

## Coverage
- meets: REPO-01, TEST-02
- not-applicable: OPS-02 (no persistent data, unlike CI-09), CI-09 (no merge queue)
"""
CATALOG_IDS = ["REPO-01", "TEST-02", "CI-02", "CI-09", "SEC-05", "OPS-02"]


class ScoringTests(unittest.TestCase):
    def test_report_statuses_read_findings_and_coverage(self):
        self.assertEqual(
            report_statuses(REPORT),
            {
                "CI-02": ["partial"],
                "SEC-05": ["pending-implementation"],
                "REPO-01": ["meets"],
                "TEST-02": ["meets"],
                "OPS-02": ["not-applicable"],
                "CI-09": ["not-applicable"],
            },
        )

    def test_coverage_accepts_one_indented_bullet_per_id(self):
        report = (
            "## Coverage\n- meets:\n  - REPO-01 (README:3 states it)\n\n"
            "  - TEST-02 deterministic, unlike CI-02\n- not-applicable:\n"
            "  - OPS-02 (no data, see CI-09)\n  - REPO-02, `AGENT-01` (no agents; unlike DEL-01)\n\n"
            "## Limitations\n  - CI-09 is not a list item here\n"
        )
        self.assertEqual(
            report_statuses(report),
            {
                "REPO-01": ["meets"],
                "TEST-02": ["meets"],
                "OPS-02": ["not-applicable"],
                "REPO-02": ["not-applicable"],
                "AGENT-01": ["not-applicable"],
            },
        )

    def test_emphasis_around_labels_ids_and_statuses_is_presentation(self):
        report = (
            "| **ID** | **Status** | Priority | Evidence |\n| --- | --- | --- | --- |\n"
            "| **CI-02** | **partial** | **high** | Inferred: tag |\n\n"
            "## Coverage\n- **meets:** REPO-01, `TEST-02`\n- __not-applicable__: OPS-02 (no data)\n"
            "  - **CI-09** (no merge queue)\n"
        )
        self.assertEqual(
            report_statuses(report),
            {
                "CI-02": ["partial"],
                "REPO-01": ["meets"],
                "TEST-02": ["meets"],
                "OPS-02": ["not-applicable"],
                "CI-09": ["not-applicable"],
            },
        )
        self.assertEqual(finding_rows(report)["CI-02"]["priority"], "high")

    def test_area_wildcards_and_several_entries_per_bullet(self):
        areas = {"AGENT": ["AGENT-01", "AGENT-02"]}
        report = (
            "## Coverage\n- meets: REPO-01, OPS-* (wildcards only close areas)\n"
            "- not-applicable areas: AGENT-* (no agents)\n- not-applicable:\n"
            "  - TEST-02 (no tests (none at all)), CI-09 (no merge queue)\n"
            "  - Delivery: DEL-01 (labels are not read)\n  - TOOL-* (not an area)\n"
        )
        self.assertEqual(
            report_statuses(report, areas),
            {
                "REPO-01": ["meets"],
                "OPS-*": ["meets"],
                "AGENT-01": ["not-applicable"],
                "AGENT-02": ["not-applicable"],
                "TEST-02": ["not-applicable"],
                "CI-09": ["not-applicable"],
                "TOOL-*": ["not-applicable"],
            },
        )

    def test_complete_report_has_no_problems(self):
        expected = {"must_find": ["CI-02", "SEC-05"], "must_not_flag": ["TEST-02"]}
        result = score(report_statuses(REPORT), CATALOG_IDS, expected)
        self.assertEqual(result["found"], ["CI-02", "SEC-05"])
        self.assertFalse(any(v for k, v in result.items() if k != "found"))

    def test_each_problem_is_reported(self):
        expected = {"must_find": ["OPS-02"], "must_not_flag": ["CI-02"]}
        report = REPORT + "| ID | Status |\n| --- | --- |\n| REPO-01 | maybe |\n| XYZ-99 | partial |\n"
        result = score(report_statuses(report), CATALOG_IDS + ["DEL-01"], expected)
        self.assertEqual(result["missed"], ["OPS-02"])
        self.assertEqual(result["false_flags"], ["CI-02"])
        self.assertEqual(result["uncovered"], ["DEL-01"])
        self.assertEqual(result["duplicated"], ["REPO-01"])
        self.assertEqual(result["unknown"], ["XYZ-99"])
        self.assertEqual(result["invalid_status"], ["REPO-01"])


PRIORITIZED = """## Findings
| ID | Status | Priority | Evidence | Improvement |
| --- | --- | --- | --- | --- |
| SEC-05 | partial | high | **Reproduced:** `settings.py:1` | Rotate |
| CI-02 | `partial` | high | `ci.yml:3` uses a tag | Pin it |
| TEST-02 | pending-implementation | low | Inferred: no tests | Add tests |
"""


class PriorityTests(unittest.TestCase):
    def test_rows_keep_priority_and_unmarked_high_findings_fail(self):
        rows = finding_rows(PRIORITIZED)
        self.assertEqual(rows["CI-02"]["priority"], "high")
        self.assertEqual(rows["TEST-02"]["status"], "pending-implementation")
        expected = {"must_find": ["SEC-05"], "must_not_flag": []}
        result = score(report_statuses(PRIORITIZED), list(rows), expected, rows)
        self.assertEqual(result["unmarked_high"], ["CI-02"])
        self.assertEqual(
            priority_summary(PRIORITIZED),
            "priorities: high 2, medium 0, low 1; high reproduced 1, inferred 0",
        )

    def test_actions_are_top_level_items_until_the_next_section(self):
        report = PRIORITIZED + (
            "\n## Priority actions\n1. **Now:** rotate (SEC-05).\n   - Scope: `settings.py`, see CI-02\n"
            "### Detail\n2. Add tests (TEST-02)\n- Later: nothing\n\n## Coverage\n1. CI-09 is not an action\n"
        )
        self.assertEqual(priority_actions(report), [["SEC-05", "CI-02"], ["TEST-02"], []])
        self.assertEqual(priority_actions(PRIORITIZED), [])

    def test_placement_reports_positions_and_extra_high_findings(self):
        report = PRIORITIZED + "\n## Priority actions\n1. Pin (CI-02)\n2. Rotate (SEC-05)\n"
        expected = {"top_priorities": ["SEC-05", "TEST-02"], "max_high": 1}
        self.assertEqual(
            priority_placement(report, expected),
            "top priorities by action (2 actions): SEC-05 2, TEST-02 -; 1 of 2 in the first five; "
            "high outside them: 1; 2 high against a case limit of 1",
        )
        self.assertIsNone(priority_placement(report, {}))

    def test_compare_reports_overlap_and_priority_differences(self):
        second = PRIORITIZED.replace("| CI-02 | `partial` | high", "| CI-02 | partial | medium")
        second = second.replace("| TEST-02 | pending-implementation", "| OPS-02 | partial")
        result = compare(PRIORITIZED, second)
        self.assertEqual(result["flagged_overlap"], (2, 4))
        self.assertEqual(result["priority_agreement"], (1, 2))
        self.assertEqual(result["priority_differences"], ["CI-02 high/medium"])
        self.assertEqual((result["only_first"], result["only_second"]), (["TEST-02"], ["OPS-02"]))


class TextCheckTests(unittest.TestCase):
    def test_leaked_values_are_reported_masked(self):
        expected = {"must_not_contain": ["fixture-secret-1", "absent-value"]}
        self.assertEqual(
            leaked("password is fixture-secret-1", expected), ["fixt... (16 characters)"]
        )
        self.assertEqual(leaked("nothing here", {}), [])

    def test_citations_outside_a_resolved_file_are_bad(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "pkg").mkdir()
            (repo / "pkg" / "app.py").write_text("a\nb\nc\n")
            (repo / "README.md").write_text("# R\ntext\n")
            text = (
                "`app.py:3` holds, `app.py:4` does not, `README.md:1-2` holds, "
                "`ci.yml:9` is unknown, `pkg/app.py:2, 5` overruns, at 22:35 nothing"
            )
            self.assertEqual(
                bad_citations(text, repo), ["app.py:4 (3 lines)", "pkg/app.py:2, 5 (3 lines)"]
            )

    def test_quoted_code_on_other_lines_marks_a_misplaced_citation(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "ci.yml").write_text("on: push\nrun: pip install x\nrun: pytest || true\n")
            text = (
                "| QUAL-03 | `ci.yml:2` runs `pytest \\|\\| true`, and `run: pip install x` (`ci.yml:2`) "
                "installs. `pip install x` (`ci.yml:3`) is wrong too. Scope: `ci.yml:1`, `run: pytest || true`. "
                "`ci.yml:3` defines `run_tests` |"
            )
            self.assertEqual(
                misplaced_citations(text, repo),
                ["ci.yml:2 (quoted code is on line 3)", "ci.yml:3 (quoted code is on line 2)"],
            )


class CaseTests(unittest.TestCase):
    def test_forbidden_strings_appear_in_their_case(self):
        for expected_path in sorted(CASES.glob("*/expected.json")):
            values = json.loads(expected_path.read_text(encoding="utf-8")).get("must_not_contain", [])
            files = [p for p in (expected_path.parent / "repo").rglob("*") if p.is_file()]
            for value in values:
                with self.subTest(case=expected_path.parent.name, value=value[:4]):
                    self.assertTrue(any(value in p.read_text(encoding="utf-8") for p in files))

    def test_cases_use_catalog_ids_without_overlap(self):
        ids = set(catalog()[0])
        for expected_path in sorted(CASES.glob("*/expected.json")):
            with self.subTest(case=expected_path.parent.name):
                expected = json.loads(expected_path.read_text(encoding="utf-8"))
                must_find, must_not = set(expected["must_find"]), set(expected["must_not_flag"])
                self.assertTrue(must_find)
                self.assertLessEqual(must_find | must_not, ids)
                self.assertFalse(must_find & must_not)
                self.assertLessEqual(set(expected.get("top_priorities", [])), must_find)
                self.assertGreaterEqual(expected.get("max_high", 0), 0)
                self.assertTrue((expected_path.parent / "repo").is_dir())

    def test_prepare_commits_a_copy_and_refuses_existing_destinations(self):
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / "case"
            (case / "repo").mkdir(parents=True)
            (case / "repo" / "README.md").write_text("# Fixture\n")
            (case / "repo" / "README.md").chmod(0o755)
            destination = Path(directory) / "audit"
            prepare(case, destination)

            def git(*arguments):
                return subprocess.run(
                    ["git", *arguments], cwd=destination, capture_output=True, text=True, check=True
                ).stdout

            self.assertEqual(git("log", "--format=%an %s"), "Evaluation Fixture Initial commit\n")
            self.assertTrue(git("ls-files", "-s", "README.md").startswith("100644 "))
            with self.assertRaises(SystemExit):
                prepare(case, destination)

            self.assertEqual(verify(case, destination), [])
            (destination / "cache").mkdir()
            (destination / "cache" / "notes.txt").write_text("left behind\n")
            self.assertEqual(verify(case, destination), ["changed: ?? cache/notes.txt"])
            git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-q",
                "--allow-empty", "-m", "extra")
            self.assertTrue(verify(case, destination)[0].startswith("HEAD is "))


if __name__ == "__main__":
    unittest.main()
