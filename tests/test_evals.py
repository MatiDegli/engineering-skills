"""Check report parsing, scoring outcomes, case consistency, and fixture preparation."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.check_skills import criteria_ids
from tools.evals import (
    CASES,
    CATALOG,
    bad_citations,
    compare,
    finding_rows,
    leaked,
    prepare,
    priority_summary,
    report_statuses,
    score,
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


class CaseTests(unittest.TestCase):
    def test_forbidden_strings_appear_in_their_case(self):
        for expected_path in sorted(CASES.glob("*/expected.json")):
            values = json.loads(expected_path.read_text(encoding="utf-8")).get("must_not_contain", [])
            files = [p for p in (expected_path.parent / "repo").rglob("*") if p.is_file()]
            for value in values:
                with self.subTest(case=expected_path.parent.name, value=value[:4]):
                    self.assertTrue(any(value in p.read_text(encoding="utf-8") for p in files))

    def test_cases_use_catalog_ids_without_overlap(self):
        catalog = set(criteria_ids(CATALOG.read_text(encoding="utf-8")))
        for expected_path in sorted(CASES.glob("*/expected.json")):
            with self.subTest(case=expected_path.parent.name):
                expected = json.loads(expected_path.read_text(encoding="utf-8"))
                must_find, must_not = set(expected["must_find"]), set(expected["must_not_flag"])
                self.assertTrue(must_find)
                self.assertLessEqual(must_find | must_not, catalog)
                self.assertFalse(must_find & must_not)
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


if __name__ == "__main__":
    unittest.main()
