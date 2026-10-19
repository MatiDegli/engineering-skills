"""Check report parsing, scoring outcomes, case consistency, and fixture preparation."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from tools import evals
from tools.evals import (
    CASES,
    bad_citations,
    catalog,
    check_seeds,
    compare,
    defect_location,
    finding_rows,
    finding_table,
    git_at,
    git_environment,
    has_problems,
    leaked,
    misplaced_citations,
    parse_date,
    prepare,
    priority_actions,
    priority_placement,
    priority_summary,
    repo_files,
    report_statuses,
    resolve_path,
    score,
    score_command,
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

    def test_a_parenthesis_inside_code_does_not_hide_later_ids(self):
        report = (
            "## Coverage\n- not-applicable:\n"
            "  - SEC-10 (no logging; `git grep 'logging|print('`), SEC-11 (no keys), `SEC-12` (no data)\n"
        )
        self.assertEqual(
            report_statuses(report),
            {identifier: ["not-applicable"] for identifier in ("SEC-10", "SEC-11", "SEC-12")},
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

    def test_deeper_checks_name_ids_without_adding_actions_or_statuses(self):
        checks = (
            "\n## Priority actions\n1. Rotate (SEC-05).\n\n## Deeper checks\n"
            "- CI-02: no gate outside CI was looked for; if one exists, medium. Check the merge docs.\n"
            "  - TEST-02 would not change.\n"
        )
        report = REPORT.replace("\n## Coverage", checks + "\n## Coverage")
        self.assertEqual(priority_actions(report), [["SEC-05"]])
        self.assertEqual(report_statuses(report), report_statuses(REPORT))

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


FIRST_ORDER = {
    "description": "The first-order rule trusts a flag that the caller sends",
    "ids": ["SEC-02", "TEST-01"],
    "at": "app/checkout.py:71-72",
    "terms": ["returning_customer", "caller"],
    "since": "2026-10-18",
}
SKU_LIST = {
    "description": "A list as a sku raises TypeError, a 500 instead of a 400",
    "ids": ["SEC-02"],
    "at": "app/checkout.py:52-53",
    "since": "2026-10-18",
}
ON_THE_DAY = date(2026, 10, 18)


def findings(*rows):
    """Build a report whose findings table has these (ID, status, evidence[, improvement]) rows."""
    header = "| ID | Status | Priority | Evidence | Improvement |\n| --- | --- | --- | --- | --- |\n"
    return "## Findings\n" + header + "".join(
        f"| {identifier} | {status} | medium | {evidence} | {''.join(improvement) or 'Fix it'} |\n"
        for identifier, status, evidence, *improvement in rows
    )


class DefectTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.repo, self.case = Path(self.directory.name) / "repo", Path(self.directory.name) / "case"
        self.case.mkdir()
        for name in ("app/checkout.py", "deploy/alerts.yaml"):
            (self.repo / name).parent.mkdir(parents=True, exist_ok=True)
            (self.repo / name).write_text("".join(f"line {n}\n" for n in range(1, 81)))

    def expected(self, *defects):
        return {"must_find": {}, "must_not_flag": {}, **({"defects": list(defects)} if defects else {})}

    def result(self, report, *defects, as_of=ON_THE_DAY):
        return score(
            report_statuses(report),
            CATALOG_IDS,
            self.expected(*defects),
            finding_rows(report),
            table=finding_table(report),
            repo=self.repo,
            as_of=as_of,
        )

    def found(self, *rows, defect=FIRST_ORDER):
        return defect["description"] in self.result(findings(*rows), defect)["defects_found"]

    def test_a_row_with_the_id_a_finding_status_the_lines_and_a_term_finds_the_defect(self):
        said = "`app/checkout.py:71` lets the caller set returning_customer"
        self.assertTrue(self.found(("SEC-02", "partial", said)))
        for status in ("pending-implementation", "pending-verification"):
            with self.subTest(status=status):
                self.assertTrue(self.found(("TEST-01", status, said)))

    def test_the_cited_path_may_be_a_unique_suffix_and_the_lines_a_list_or_a_range_that_overlaps(self):
        for evidence in (
            "`checkout.py:72` trusts the caller",
            "`app/checkout.py:60-71` trusts the caller",
            "`app/checkout.py:72-90` trusts the caller",
            "`app/checkout.py:5, 72` trusts the caller",
            "`app/checkout.py:1-80` trusts the caller",
            "`app/checkout.py:71-72` trusts the caller",
        ):
            with self.subTest(evidence=evidence):
                self.assertTrue(self.found(("SEC-02", "partial", evidence)))

    def test_the_right_lines_under_another_id_do_not_find_the_defect(self):
        said = "`app/checkout.py:71` trusts the caller's returning_customer flag"
        self.assertFalse(self.found(("TEST-02", "partial", said)))
        self.assertFalse(self.found(("SEC-03", "pending-implementation", said)))
        elsewhere = ("SEC-02", "partial", "`app/checkout.py:12` is unsafe")
        self.assertFalse(self.found(elsewhere, ("TEST-02", "partial", said)))

    def test_a_status_that_is_not_a_finding_does_not_find_the_defect(self):
        said = "`app/checkout.py:71` trusts the caller's returning_customer flag"
        for status in ("meets", "not-applicable"):
            with self.subTest(status=status):
                self.assertFalse(self.found(("SEC-02", status, said)))

    def test_the_right_id_citing_other_lines_or_files_does_not_find_the_defect(self):
        for evidence in (
            "`app/checkout.py:70` trusts the caller",
            "`app/checkout.py:73-80` trusts the caller",
            "`app/checkout.py:1-70` trusts the caller",
            "`deploy/alerts.yaml:71` trusts the caller",
            "`app/missing.py:71` trusts the caller",
            "trusts the caller",
        ):
            with self.subTest(evidence=evidence):
                self.assertFalse(self.found(("SEC-02", "partial", evidence)))

    def test_the_right_id_and_lines_without_a_term_do_not_find_the_defect(self):
        self.assertFalse(self.found(("SEC-02", "partial", "`app/checkout.py:71` is unsafe")))
        self.assertTrue(self.found(("SEC-02", "partial", "`app/checkout.py:71` trusts the CALLER")))
        loose = {key: value for key, value in FIRST_ORDER.items() if key != "terms"}
        self.assertTrue(self.found(("SEC-02", "partial", "`app/checkout.py:71` is unsafe"), defect=loose))

    def test_any_cell_of_the_row_may_cite_the_lines_and_carry_a_term(self):
        row = ("SEC-02", "partial", "the flag", "`app/checkout.py:71` trusts the caller")
        self.assertTrue(self.found(row))
        self.assertTrue(self.found(("SEC-02", "partial", "`app/checkout.py:71`", "Validate it, the caller lies")))

    def test_a_citation_without_a_line_number_does_not_count(self):
        for evidence in (
            "`app/checkout.py` trusts the caller",
            "app/checkout.py: trusts the caller",
            "`checkout.py` trusts the caller; see line 71",
        ):
            with self.subTest(evidence=evidence):
                self.assertFalse(self.found(("SEC-02", "partial", evidence)))

    def test_one_row_must_meet_every_condition(self):
        rows = [
            ("SEC-02", "partial", "`app/checkout.py:71` is unsafe"),
            ("SEC-02", "partial", "the caller is trusted, see `app/checkout.py:12`"),
            ("TEST-01", "partial", "`app/checkout.py:72` is not tested"),
        ]
        self.assertFalse(self.found(*rows))
        self.assertTrue(self.found(*rows, ("SEC-02", "partial", "`app/checkout.py:71` trusts the caller")))

    def test_a_row_that_repeats_an_id_does_not_hide_another_defect(self):
        report = findings(
            ("SEC-02", "partial", "`app/checkout.py:71` trusts the caller"),
            ("SEC-02", "partial", "`app/checkout.py:53` raises TypeError, a 500"),
        )
        result = self.result(report, FIRST_ORDER, SKU_LIST)
        self.assertEqual(result["defects_found"], [FIRST_ORDER["description"], SKU_LIST["description"]])
        self.assertEqual(result["defects_missed"], [])

    def test_a_path_that_names_several_files_is_not_resolved(self):
        (self.repo / "legacy").mkdir()
        (self.repo / "legacy" / "checkout.py").write_text("old\n" * 80)
        self.assertFalse(self.found(("SEC-02", "partial", "`checkout.py:71` trusts the caller")))
        self.assertTrue(self.found(("SEC-02", "partial", "`app/checkout.py:71` trusts the caller")))
        files = repo_files(self.repo)
        self.assertIsNone(resolve_path("checkout.py", files))
        self.assertEqual(resolve_path("alerts.yaml", files), "deploy/alerts.yaml")
        self.assertEqual(resolve_path("legacy/checkout.py", files), "legacy/checkout.py")

    def test_a_numeric_term_matches_only_the_whole_number(self):
        sku = {**SKU_LIST, "ids": ["TEST-01"], "terms": ["500"]}
        limits = "Nothing tests the limits at `app/checkout.py:36-59`, such as taxable 4999/5000"
        self.assertFalse(self.found(("TEST-01", "partial", limits), defect=sku))
        crash = "A list sku at `app/checkout.py:53` returns 500, not 400"
        self.assertTrue(self.found(("TEST-01", "partial", crash), defect=sku))

    def test_a_test_gap_at_the_lines_is_not_the_defect_but_the_trusted_flag_is(self):
        welcome = {
            "description": "The WELCOME10 first-order rule trusts the returning_customer flag",
            "ids": ["SEC-02", "TEST-01", "ARCH-02", "REPO-06"],
            "at": "app/checkout.py:71-72",
            "terms": ["returning_customer", "caller", "client", "payload", "self-reported", "trusts"],
        }
        gap = findings(("TEST-01", "partial", "Nothing tests the WELCOME10 rule at `checkout.py:71`"))
        flag = findings(
            ("TEST-01", "partial", "`checkout.py:71`: the rule trusts the caller's returning_customer flag")
        )
        self.assertEqual(self.result(gap, welcome)["defects_found"], [])
        self.assertEqual(self.result(flag, welcome)["defects_found"], [welcome["description"]])

    def test_a_defect_counts_only_from_its_since_date(self):
        report = findings(("SEC-02", "partial", "`app/checkout.py:71` trusts the caller"))
        undated = {key: value for key, value in FIRST_ORDER.items() if key != "since"}
        for as_of, counted in ((date(2026, 10, 17), 0), (ON_THE_DAY, 1), (date(2026, 10, 19), 1)):
            with self.subTest(as_of=as_of):
                result = self.result(report, FIRST_ORDER, as_of=as_of)
                self.assertEqual(result["defects_counted"], [FIRST_ORDER["description"]] * counted)
                self.assertEqual(result["defects_found"], [FIRST_ORDER["description"]] * counted)
                self.assertEqual(result["defects_missed"], [])
        self.assertEqual(
            self.result(report, undated, as_of=date(2000, 1, 1))["defects_found"], [undated["description"]]
        )

    def test_a_missed_defect_is_counted_and_listed_by_description(self):
        report = findings(("SEC-02", "partial", "`app/checkout.py:71` trusts the caller"))
        result = self.result(report, FIRST_ORDER, SKU_LIST)
        self.assertEqual(result["defects_found"], [FIRST_ORDER["description"]])
        self.assertEqual(result["defects_missed"], [SKU_LIST["description"]])
        self.assertEqual(result["defects_counted"], [FIRST_ORDER["description"], SKU_LIST["description"]])

    def test_a_case_without_defects_scores_without_a_repository(self):
        result = score(report_statuses(REPORT), CATALOG_IDS, self.expected())
        self.assertEqual(
            (result["defects_found"], result["defects_missed"], result["defects_counted"]), ([], [], [])
        )
        with self.assertRaises(ValueError):
            score({}, CATALOG_IDS, self.expected(FIRST_ORDER), as_of=ON_THE_DAY)

    def test_the_date_defaults_to_today_in_utc(self):
        report = findings(("SEC-02", "partial", "`app/checkout.py:71` trusts the caller"))
        arguments = (report_statuses(report), CATALOG_IDS, self.expected(FIRST_ORDER))
        keywords = {"table": finding_table(report), "repo": self.repo}
        with mock.patch.object(evals, "today", return_value=date(2026, 10, 17)):
            self.assertEqual(score(*arguments, **keywords)["defects_counted"], [])
        with mock.patch.object(evals, "today", return_value=ON_THE_DAY):
            self.assertEqual(score(*arguments, **keywords)["defects_found"], [FIRST_ORDER["description"]])

    def test_dates_are_year_month_day_and_nothing_looser(self):
        self.assertEqual(parse_date("2026-10-18"), ON_THE_DAY)
        for value in ("20261018", "2026-1-8", "2026-13-01", "18/10/2026", "2026-10-18T00:00"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_date(value)

    def test_a_location_is_a_path_with_one_ascending_range(self):
        self.assertEqual(defect_location("app/checkout.py:71-72"), ("app/checkout.py", 71, 72))
        self.assertEqual(defect_location("deploy/alerts.yaml:5"), ("deploy/alerts.yaml", 5, 5))
        for value in ("app/checkout.py", "app/checkout.py:72-71", "app/checkout.py:0", "a.py:1, 3"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    defect_location(value)

    def test_the_score_command_reports_defects_only_when_the_case_counts_one(self):
        report = self.case / "report.md"
        report.write_text(findings(("SEC-02", "partial", "`app/checkout.py:71` trusts the caller")))

        def printed(*defects, as_of=ON_THE_DAY):
            (self.case / "expected.json").write_text(json.dumps(self.expected(*defects)))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                score_command(report, self.case, self.repo, as_of)
            return output.getvalue()

        both = printed(FIRST_ORDER, SKU_LIST)
        self.assertIn("Found 1 of 2 seeded defects at their location.\n", both)
        self.assertIn(f"defects not found (not a failure): {SKU_LIST['description']}\n", both)
        self.assertIn("Found 1 of 1 seeded defects at their location.\n", printed(FIRST_ORDER))
        self.assertNotIn("seeded defects", printed(FIRST_ORDER, as_of=date(2026, 10, 17)))
        self.assertNotIn("seeded defects", printed())
        self.assertNotIn("defects not found", printed())

    def test_missed_defects_are_measures_that_never_fail_a_report(self):
        everything = catalog()[0]
        report = findings(("SEC-02", "partial", "`app/checkout.py:12`")) + (
            "\n## Coverage\n- meets: " + ", ".join(i for i in everything if i != "SEC-02") + "\n"
        )
        result = score(
            report_statuses(report),
            everything,
            self.expected(FIRST_ORDER),
            finding_rows(report),
            table=finding_table(report),
            repo=self.repo,
            as_of=ON_THE_DAY,
        )
        self.assertEqual(result["defects_missed"], [FIRST_ORDER["description"]])
        self.assertFalse(has_problems(result), result)
        self.assertTrue(has_problems(result | {"false_flags": ["SEC-09"]}))
        (self.case / "report.md").write_text(report)
        (self.case / "expected.json").write_text(json.dumps(self.expected(FIRST_ORDER)))
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(score_command(self.case / "report.md", self.case, self.repo, ON_THE_DAY), 0)


def defect_problems(defects, ids, repo):
    """Return what is wrong with a case's seeded defects; `repo` is the case's repository."""
    if not isinstance(defects, list):
        return ["defects must be a list"]
    problems, descriptions, files = [], set(), repo_files(repo)
    for number, defect in enumerate(defects, 1):
        name = f"defect {number}"
        if not isinstance(defect, dict):
            problems.append(f"{name} must be an object")
            continue
        for key in sorted(set(defect) - {"description", "ids", "at", "terms", "since"}):
            problems.append(f"{name} has an unknown field {key}")
        description = defect.get("description")
        if not isinstance(description, str) or not description.strip():
            problems.append(f"{name} needs a description")
        elif description in descriptions:
            problems.append(f"{name} repeats the description {description!r}")
        else:
            descriptions.add(description)
        listed = defect.get("ids")
        if not (isinstance(listed, list) and listed and all(isinstance(i, str) and i in ids for i in listed)):
            problems.append(f"{name} needs ids that are all in the catalog")
        try:
            path, _, last = defect_location(defect.get("at", ""))
        except (TypeError, ValueError) as error:
            problems.append(f"{name} has a bad location: {error}")
        else:
            target = resolve_path(path, files)
            if target is None:
                problems.append(f"{name} locates {path}, which is not one file of the repository")
            elif last > len(files[target].read_text(encoding="utf-8").splitlines()):
                problems.append(f"{name} locates lines past the end of {target}")
        if "since" in defect:
            try:
                parse_date(defect["since"])
            except (TypeError, ValueError):
                problems.append(f"{name} has a since that is not a YYYY-MM-DD date")
        terms = defect.get("terms")
        if "terms" in defect and (
            not isinstance(terms, list) or not terms or not all(isinstance(t, str) and t.strip() for t in terms)
        ):
            problems.append(f"{name} needs terms that are non-empty strings")
    return problems


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
                self.assertEqual(
                    defect_problems(expected.get("defects", []), ids, expected_path.parent / "repo"), []
                )

    def test_seeded_defects_need_a_description_catalog_ids_a_location_and_valid_fields(self):
        ids = set(catalog()[0])
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "app").mkdir()
            (repo / "app" / "checkout.py").write_text("one\ntwo\nthree\n")
            good = {
                "description": "A defect",
                "ids": ["SEC-02"],
                "at": "app/checkout.py:2-3",
                "terms": ["term"],
                "since": "2026-10-18",
            }
            self.assertEqual(defect_problems([good, good | {"description": "Another"}], ids, repo), [])
            bare = {k: v for k, v in good.items() if k not in ("terms", "since")}
            self.assertEqual(defect_problems([bare], ids, repo), [])
            bad = {
                "no description": {"description": ""},
                "blank description": {"description": "  "},
                "repeated description": {"description": "A defect"},
                "no ids": {"ids": []},
                "unknown id": {"ids": ["SEC-02", "ZZZ-99"]},
                "ids that are not text": {"ids": [2]},
                "no location": {"at": None},
                "location without a line": {"at": "app/checkout.py"},
                "location in no file": {"at": "app/missing.py:1"},
                "location past the end": {"at": "app/checkout.py:3-4"},
                "location before the start": {"at": "app/checkout.py:0-1"},
                "since that is not a date": {"since": "18/10/2026"},
                "since that is not text": {"since": 20261018},
                "no terms": {"terms": []},
                "blank term": {"terms": ["term", " "]},
                "terms that are not a list": {"terms": "term"},
                "unknown field": {"term": ["term"]},
            }
            for name, change in bad.items():
                with self.subTest(name):
                    defects = [good, good | {"description": "Second"} | change]
                    problems = defect_problems(defects, ids, repo)
                    self.assertEqual(len(problems), 1, problems)
                    self.assertTrue(problems[0].startswith("defect 2 "), problems)
            self.assertEqual(defect_problems({"description": "x"}, ids, repo), ["defects must be a list"])
            self.assertEqual(defect_problems(["x"], ids, repo), ["defect 1 must be an object"])

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


IDENTITY = {
    "GIT_AUTHOR_NAME": "Source Author",
    "GIT_AUTHOR_EMAIL": "author@example.invalid",
    "GIT_COMMITTER_NAME": "Source Author",
    "GIT_COMMITTER_EMAIL": "author@example.invalid",
}


def run_git(directory, *arguments, date="2026-01-01T00:00:00Z", check=True):
    environment = git_environment(**IDENTITY, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    return subprocess.run(
        ["git", *arguments], cwd=directory, env=environment, capture_output=True, text=True, check=check
    ).stdout


def commit_files(repository, message, files, date):
    for name, content in files.items():
        path = repository / name
        if content is None:
            path.unlink()
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    run_git(repository, "add", "-A")
    run_git(repository, "commit", "-q", "-m", message, date=date)


def source_repository(root):
    """Build a history with a merge, where the side branch last changes b/two.txt, and a revert
    that brings b/back.txt back to the content it had two commits earlier."""
    repository = root / "source"
    repository.mkdir()
    run_git(repository, "init", "-q", "-b", "main")
    commit_files(repository, "add one", {"README.md": "# Source\n", "a/one.txt": "one\n"}, "2026-01-01T00:00:00Z")
    commit_files(repository, "add two", {"b/two.txt": "two\n", "b/back.txt": "B\n"}, "2026-01-02T00:00:00Z")
    commit_files(repository, "change one", {"a/one.txt": "one v2\n", "b/back.txt": "C\n"}, "2026-01-03T00:00:00Z")
    run_git(repository, "checkout", "-q", "-b", "side")
    commit_files(repository, "change two", {"b/two.txt": "two side\n"}, "2026-01-04T00:00:00Z")
    run_git(repository, "checkout", "-q", "main")
    commit_files(repository, "change readme", {"README.md": "# Source v2\n", "b/back.txt": "B\n"}, "2026-01-05T00:00:00Z")
    run_git(repository, "merge", "-q", "--no-ff", "-m", "merge side", "side", date="2026-01-06T00:00:00Z")
    (repository / "c").mkdir()
    (repository / "c" / "link").symlink_to("three.txt")
    commit_files(repository, "add c", {"c/three.txt": "three\n"}, "2026-01-07T00:00:00Z")
    run_git(repository, "tag", "v1", "HEAD~2")
    run_git(repository, "checkout", "-q", "-b", "draft")
    commit_files(repository, "draft", {"a/one.txt": "one draft\n"}, "2026-01-08T00:00:00Z")
    run_git(repository, "checkout", "-q", "main")
    return repository


class SourceCaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.source = source_repository(self.root)
        self.case = self.root / "case"
        (self.case / "seed" / "a").mkdir(parents=True)
        (self.case / "seed" / "a" / "one.txt").write_text("one SEEDED\n")
        (self.case / "seed" / "a" / "new.txt").write_text("new SEEDED\n")
        (self.case / "seed" / "b").mkdir()
        (self.case / "seed" / "b" / "back.txt").write_text("B SEEDED\n")
        (self.case / "expected.json").write_text('{"must_find": ["REPO-01"], "must_not_flag": []}')
        self.write_source(remove=["b/two.txt"])

    def tearDown(self):
        self.directory.cleanup()

    def write_source(self, **fields):
        head = run_git(self.source, "rev-parse", "main").strip()
        (self.case / "source.json").write_text(
            json.dumps({"repository": str(self.source), "commit": head, **fields})
        )

    def source_state(self):
        return (
            run_git(self.source, "for-each-ref"),
            run_git(self.source, "status", "--porcelain", "--ignored"),
            run_git(self.source, "reflog", "--all"),
        )

    def test_seeds_fold_into_the_commits_that_last_touched_their_paths(self):
        before = self.source_state()
        destination = self.root / "audit"
        prepare(self.case, destination)

        def git(*arguments):
            return run_git(destination, *arguments)

        self.assertEqual(before, self.source_state())
        self.assertEqual(git("log", "--format=%s"), run_git(self.source, "log", "--format=%s"))
        self.assertEqual((destination / "a" / "one.txt").read_text(), "one SEEDED\n")
        self.assertEqual(git("log", "-1", "--format=%s", "--", "a/one.txt"), "change one\n")
        self.assertEqual(git("log", "--diff-filter=A", "--format=%s", "--", "a/new.txt"), "change one\n")
        self.assertFalse((destination / "b" / "two.txt").exists())
        self.assertEqual(git("log", "--diff-filter=D", "--format=%s", "--", "b/two.txt"), "change two\n")
        self.assertEqual(git("show", "HEAD~2:a/one.txt"), "one SEEDED\n")
        untouched = run_git(self.source, "rev-list", "--reverse", "main")[:41]
        self.assertTrue(git("rev-list", "--reverse", "main").startswith(untouched))
        for path, content in (("a/one.txt", "one v2\n"), ("b/back.txt", "B\n"), ("b/two.txt", "two side\n")):
            for commit in git("rev-list", "--all").split():
                with self.subTest(path=path, commit=commit[:7]):
                    self.assertNotEqual(run_git(destination, "show", f"{commit}:{path}", check=False), content)
        seeded = [destination / p for p in ("a/one.txt", "a/new.txt", "b/back.txt")]
        others = [destination / p for p in ("README.md", "c/three.txt")]
        newest = max(p.stat().st_mtime_ns for p in others)
        self.assertLessEqual(max(p.stat().st_mtime_ns for p in seeded), newest)
        self.assertFalse((destination / ".git" / "refs" / "original").exists())
        self.assertTrue((destination / ".git" / "description").exists())

        self.assertEqual(git("for-each-ref", "--format=%(refname)"), "refs/heads/main\n")
        self.assertEqual(git("remote"), "")
        self.assertEqual(git("reflog", "--all"), "")
        self.assertEqual(git("fsck", "--unreachable", "--no-reflogs"), "")
        self.assertFalse((destination / ".git" / "ORIG_HEAD").exists())
        self.assertNotIn(str(self.source), (destination / ".git" / "config").read_text())
        self.assertEqual(git("status", "--porcelain", "--ignored"), "")
        self.assertEqual(verify(self.case, destination), [])

    def test_branches_keeps_the_source_branches_not_newer_than_the_pin_as_local_branches(self):
        shutil.rmtree(self.case / "seed")
        commit = lambda name: run_git(self.source, "rev-parse", name).strip()
        # The pin is the merge, which the local main and draft branches postdate.
        pinned, side, older = commit("main~1"), commit("side"), commit("main~2")
        upstream = "refs/remotes/upstream"
        remote = {"release": older, "stable": pinned, "side": commit("main~4"), "main": older}
        for name, head in (remote | {"next": commit("main")}).items():
            run_git(self.source, "update-ref", f"{upstream}/{name}", head)
        run_git(self.source, "symbolic-ref", f"{upstream}/HEAD", f"{upstream}/main")
        self.write_source(commit=pinned)
        prepare(self.case, self.root / "plain")
        plain = run_git(self.root / "plain", "for-each-ref", "--format=%(refname)")
        self.assertEqual(plain, "refs/heads/main\n")
        self.write_source(commit=pinned, branches=True)
        destination = self.root / "audit"
        prepare(self.case, destination)

        def git(*arguments):
            return run_git(destination, *arguments)

        # Local main and draft, and the remote's next, are newer than the pin; the remote's main
        # names the pinned branch; the local side wins over the remote's.
        kept = {"main": pinned, "release": older, "side": side, "stable": pinned}
        listed = "".join(f"refs/heads/{name} {head}\n" for name, head in kept.items())
        self.assertEqual(git("for-each-ref", "--format=%(refname) %(objectname)"), listed)
        self.assertEqual(git("rev-parse", "HEAD").strip(), pinned)
        self.assertEqual(git("remote"), "")
        self.assertEqual(git("reflog", "--all"), "")
        self.assertEqual(git("fsck", "--unreachable", "--no-reflogs"), "")
        self.assertNotIn(str(self.source), (destination / ".git" / "config").read_text())
        self.assertEqual(git("status", "--porcelain", "--ignored"), "")
        self.assertEqual(verify(self.case, destination), [])
        git("update-ref", "refs/heads/release", pinned)
        git("update-ref", "-d", "refs/heads/stable")
        moved = f"branch release is {pinned[:7]}, expected {older[:7]}"
        deleted = f"branch stable is missing, expected {pinned[:7]}"
        self.assertEqual(verify(self.case, destination), [moved, deleted])

    def test_branches_are_refused_with_seeds(self):
        variants = {"seed": {}, "remove": {"remove": ["b/two.txt"]}}
        for name, fields in (variants | {"executable": {"executable": ["x"]}}).items():
            with self.subTest(name=name):
                if name != "seed":
                    shutil.rmtree(self.case / "seed", ignore_errors=True)
                self.write_source(branches=True, **fields)
                with self.assertRaisesRegex(SystemExit, "`branches` with seeds"):
                    prepare(self.case, self.root / f"audit-{name}")
                self.assertFalse((self.root / f"audit-{name}").exists())

    def test_preparation_is_deterministic_and_refuses_unpinned_sources(self):
        heads = []
        for name in ("first", "second"):
            prepare(self.case, self.root / name)
            heads.append(run_git(self.root / name, "rev-parse", "HEAD"))
        self.assertEqual(heads[0], heads[1])
        self.write_source(commit="main")
        with self.assertRaises(SystemExit):
            prepare(self.case, self.root / "third")

    def test_a_failed_clone_never_touches_an_enclosing_repository(self):
        outer = self.root / "outer"
        outer.mkdir()
        run_git(outer, "init", "-q", "-b", "main")
        commit_files(outer, "outer", {"keep.txt": "keep\n"}, "2026-02-01T00:00:00Z")
        state = run_git(outer, "log", "--format=%H %s"), run_git(outer, "for-each-ref")
        self.write_source()
        source = json.loads((self.case / "source.json").read_text())
        (self.case / "source.json").write_text(
            json.dumps({**source, "repository": str(self.root / "missing")})
        )
        with self.assertRaises((SystemExit, subprocess.CalledProcessError)):
            prepare(self.case, outer / "nested" / "audit")
        self.assertEqual(state, (run_git(outer, "log", "--format=%H %s"), run_git(outer, "for-each-ref")))
        self.assertEqual(run_git(outer, "status", "--porcelain"), "")

    def test_seed_paths_stay_inside_the_repository(self):
        paths = ("../escape.txt", ".git/config", "a/*.txt", "a/./one.txt", ":(literal)README.md")
        for number, path in enumerate(paths + ("a/.git/hooks/x", "README.md/inner.txt")):
            with self.subTest(path=path):
                self.write_source(remove=[path])
                with self.assertRaises(SystemExit):
                    prepare(self.case, self.root / f"audit-{number}")
                self.assertFalse((self.root / f"audit-{number}").exists())
        self.write_source()
        (self.case / "seed" / "a" / "link.txt").symlink_to(self.root / "outside.txt")
        with self.assertRaises(SystemExit):
            prepare(self.case, self.root / "audit-link")

    def test_seeds_that_would_hide_nothing_or_break_the_tree_are_refused(self):
        variants = {
            "parent-file": lambda: (self.case / "seed" / "README.md").mkdir(),
            "symlink-replaced": lambda: (self.case / "seed" / "c").mkdir(),
            "same-content": lambda: None,
            "undeclared-executable": lambda: None,
        }
        for name, setup in variants.items():
            with self.subTest(name=name):
                self.tearDown()
                self.setUp()
                setup()
                if name == "parent-file":
                    (self.case / "seed" / "README.md" / "inner.txt").write_text("x\n")
                if name == "symlink-replaced":
                    (self.case / "seed" / "c" / "link").write_text("regular\n")
                if name == "same-content":
                    (self.case / "seed" / "c").mkdir()
                    (self.case / "seed" / "c" / "three.txt").write_text("three\n")
                    with self.assertRaisesRegex(SystemExit, "equals its content"):
                        prepare(self.case, self.root / "audit")
                if name == "undeclared-executable":
                    self.write_source(remove=["b/two.txt"], executable=["c/missing.txt"])
                with self.assertRaises(SystemExit):
                    prepare(self.case, self.root / "audit")
                self.assertFalse((self.root / "audit").exists())

    def test_renames_and_emptied_fix_commits_are_refused(self):
        commit_files(self.source, "add old", {"d/old.py": "safe\n"}, "2026-01-09T00:00:00Z")
        run_git(self.source, "mv", "d/old.py", "d/new.py")
        run_git(self.source, "commit", "-q", "-m", "rename old", date="2026-01-10T00:00:00Z")
        self.write_source(remove=["b/two.txt"])
        (self.case / "seed" / "d").mkdir()
        (self.case / "seed" / "d" / "new.py").write_text("unsafe\n")
        with self.assertRaisesRegex(SystemExit, "d/old.py"):
            prepare(self.case, self.root / "renamed")
        (self.case / "seed" / "d" / "new.py").unlink()
        commit_files(self.source, "add view", {"e/view.py": "vulnerable\n"}, "2026-01-11T00:00:00Z")
        commit_files(self.source, "fix view", {"e/view.py": "fixed\n"}, "2026-01-12T00:00:00Z")
        self.write_source(remove=["b/two.txt"])
        (self.case / "seed" / "e").mkdir()
        (self.case / "seed" / "e" / "view.py").write_text("vulnerable\n")
        with self.assertRaisesRegex(SystemExit, "fix view"):
            prepare(self.case, self.root / "emptied")
        self.assertFalse((self.root / "emptied").exists())

    def test_relative_and_shallow_sources(self):
        self.write_source(remove=["b/two.txt"], repository="../source")
        directory = os.getcwd()
        try:
            os.chdir("/")
            prepare(self.case, self.root / "relative")
        finally:
            os.chdir(directory)
        shallow = self.root / "shallow"
        run_git(self.root, "clone", "-q", "--depth", "1", f"file://{self.source}", str(shallow))
        head = run_git(shallow, "rev-parse", "HEAD").strip()
        (self.case / "source.json").write_text(json.dumps({"repository": str(shallow), "commit": head}))
        with self.assertRaisesRegex(SystemExit, "shallow"):
            prepare(self.case, self.root / "from-shallow")

    def test_an_existing_destination_is_never_removed(self):
        destination = self.root / "taken"
        destination.mkdir()
        (destination / "work.txt").write_text("someone else's\n")
        with self.assertRaises(SystemExit):
            evals.prepare_from_source(self.case, destination)
        self.assertEqual((destination / "work.txt").read_text(), "someone else's\n")
        late, real_mkdir = self.root / "late", os.mkdir

        def taken_meanwhile(path, *arguments, **options):
            if Path(path) != late:
                return real_mkdir(path, *arguments, **options)
            real_mkdir(path)
            (late / "work.txt").write_text("another preparation's\n")
            raise FileExistsError(path)

        with mock.patch.object(evals.os, "mkdir", taken_meanwhile):
            with self.assertRaises(FileExistsError):
                evals.prepare_from_source(self.case, late)
        self.assertEqual((late / "work.txt").read_text(), "another preparation's\n")

    def test_failures_leave_no_destination_and_never_write_inside_the_source(self):
        before = self.source_state()
        with self.assertRaises(SystemExit):
            prepare(self.case, self.source / "inside")
        self.write_source(commit="0" * 40)
        with self.assertRaises(subprocess.CalledProcessError):
            prepare(self.case, self.root / "audit")
        self.assertFalse((self.root / "audit").exists())
        self.assertEqual(before, self.source_state())
        self.assertFalse((self.source / "inside").exists())

    def test_a_failure_after_the_clone_removes_the_destination(self):
        def failing_gc(git_dir, *arguments, **options):
            if "gc" in arguments:
                raise subprocess.CalledProcessError(1, ["git", "gc"])
            return git_at(git_dir, *arguments, **options)

        with mock.patch.object(evals, "git_at", failing_gc):
            with self.assertRaises(subprocess.CalledProcessError):
                prepare(self.case, self.root / "audit")
        self.assertFalse((self.root / "audit").exists())

    def test_seed_checks_reject_a_missing_seed_and_kept_pinned_content(self):
        destination = self.root / "audit"
        prepare(self.case, destination)

        def git(*arguments, **options):
            return git_at(destination / ".git", *arguments, work_tree=destination, **options)

        blob = lambda content: git("hash-object", "--stdin", stdin=content).strip()
        seeded = ("100644", blob("one SEEDED\n"))
        check_seeds(git, {"a/one.txt": (seeded, blob("one v2\n"))})
        with self.assertRaises(SystemExit):
            check_seeds(git, {"a/one.txt": (("100644", blob("other\n")), None)})
        with self.assertRaises(SystemExit):
            check_seeds(git, {"a/one.txt": (seeded, blob("one\n"))})

    def test_new_files_are_executable_only_when_declared(self):
        (self.case / "seed" / "a" / "new.txt").chmod(0o755)
        prepare(self.case, self.root / "plain")
        self.assertTrue(run_git(self.root / "plain", "ls-files", "-s", "a/new.txt").startswith("100644 "))
        self.write_source(remove=["b/two.txt"], executable=["a/new.txt"])
        prepare(self.case, self.root / "declared")
        self.assertTrue(run_git(self.root / "declared", "ls-files", "-s", "a/new.txt").startswith("100755 "))

    def test_the_callers_git_variables_and_settings_change_nothing(self):
        prepare(self.case, self.root / "reference")
        outer = self.root / "outer"
        outer.mkdir()
        run_git(outer, "init", "-q", "-b", "main")
        commit_files(outer, "outer", {"keep.txt": "keep\n"}, "2026-02-01T00:00:00Z")
        files = lambda: {p: p.read_bytes() for p in sorted((outer / ".git").rglob("*")) if p.is_file()}
        before = files()
        hooks = self.root / "hooks"
        hooks.mkdir()
        (hooks / "post-checkout").write_text(f"#!/bin/sh\ntouch {self.root / 'hook-ran'}\n")
        (hooks / "post-checkout").chmod(0o755)
        home = self.root / "home"
        (home / "git").mkdir(parents=True)
        settings = f"[core]\n\thooksPath = {hooks}\n[i18n]\n\tcommitEncoding = ISO-8859-1\n"
        (home / ".gitconfig").write_text(settings)
        (home / "git" / "attributes").write_text("* text eol=crlf\n*.txt ident\n")
        exported = {
            "GIT_INDEX_FILE": str(outer / ".git" / "index"),
            "GIT_OBJECT_DIRECTORY": str(outer / ".git" / "objects"),
            "GIT_WORK_TREE": str(outer),
            "GIT_CONFIG_GLOBAL": str(home / ".gitconfig"),
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home),
        }
        with mock.patch.dict(os.environ, exported):
            prepare(self.case, self.root / "audit")
        self.assertEqual(before, files())
        self.assertFalse((self.root / "hook-ran").exists())
        self.assertEqual((self.root / "audit" / "README.md").read_bytes(), b"# Source v2\n")
        heads = [run_git(self.root / name, "rev-parse", "HEAD") for name in ("reference", "audit")]
        self.assertEqual(heads[0], heads[1])


if __name__ == "__main__":
    unittest.main()
