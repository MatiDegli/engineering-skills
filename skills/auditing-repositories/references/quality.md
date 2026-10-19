# Engineering quality

Choose controls that detect problems in the project. Each control needs a scope, configuration,
local command, and CI execution, and it must reject an invalid case, which whoever adds or audits
the control checks by trying one. The following guidance complements the
[standard](standard.md); implementation belongs to the project.

## Contents

- [Controls by stack](#controls-by-stack)
- [Starting limits](#starting-limits)
- [Scope and exceptions](#scope-and-exceptions)
- [Guards and hooks](#guards-and-hooks)
- [Rules for changes and agents](#rules-for-changes-and-agents)
- [Dependency maintenance](#dependency-maintenance)

## Controls by stack

| Stack | Starting point |
| --- | --- |
| Python | uv and lockfile; Ruff for format/lint; strict mypy or Pyright; pytest and coverage.py with branches |
| TypeScript | Package manager with lockfile; strict compiler; format/lint with compatible tools; behavioral tests |
| Maintained JavaScript | strict TS or `allowJs`/`checkJs` and JSDoc; include scripts and tests |
| Rust | rustfmt, Clippy, tests, and lockfile review |
| Shell / PowerShell | ShellCheck / PSScriptAnalyzer; test behavior on supported platforms |

Enable relevant rules and check their severity and exit code. Avoid `ALL`, global ignores, two
formatters, or two typecheckers without a demonstrated need.
In pytest, reject unknown configuration and markers. Choose specialized tools from the
[catalog](tooling.md#quality-and-testing).

## Starting limits

Agree on numbers and counting method before blocking CI. For Python, this reference uses physical
lines containing code: it excludes blanks, comments, and docstrings; it includes data literals,
decorators, and nested code within its containing unit.

| Unit | SLOC warning | Block when exceeded |
| --- | --- | --- |
| Production or tooling file | 300 | 450 |
| Function/method | 40 | 60 |
| Class | 200 | 300 |
| Test file | 500 | 700 |
| Test function | 70 | 100 |

Other starting values to review: maximum cyclomatic complexity 10, arguments 5, branches 10,
returns 6, and statements 50. These are design signals, as are surviving mutants that cluster in one
unit (see [useful tests](validation.md#useful-tests)); avoid fragmenting a responsibility or
creating giant files to satisfy a number. The number of files per directory has its own
[review criterion](structure.md).

If adopting a coverage threshold, measure branches and test the boundary with the actual tool.
For example, in coverage.py a combined target of 90% needs enough precision to reject 89.70% and
accept 90.00%. This combined target does not enforce 90% separately for lines and branches. Coverage
identifies gaps and does not by itself prove that tests are useful. Cyclomatic complexity, cognitive
complexity, and SLOC measure different things: do not transfer their numbers across languages.
Configure blocking severity where appropriate and check the exit code.

## Scope and exceptions

- Include maintained source, scripts, tests, new extensions, and uncommitted files. Exclude generated
  files, vendor content, and evidence using explicit paths and purposes.
- Test that new, renamed, or ignored files do not escape the adopted control.
- Each exception identifies a path/symbol, rule, reason, owner, and removal condition.
- For inherited debt, set caps that forbid growth, reduce them as the code improves, and remove obsolete
  entries. A committed baseline of known violations is such a cap when CI fails on a new violation and
  an added entry needs its own reviewed change. Avoid baselines that regenerate themselves and
  configurations that nullify the control.
- Record known technical debt in one register with an owner, its impact, and a removal condition.
  Review the register on a schedule and link exceptions and TODOs to their entries.
- A migration from one pattern to another, such as a helper that a decision retires, names its
  completion condition, and a check rejects new uses of the old pattern while the known ones shrink;
  otherwise each new change copies whichever pattern it finds first.
- Change regenerable contracts at their source. Compare bytes and file sets in a temporary destination
  to detect differences, missing files, and extras.

## Guards and hooks

A guard or hook that blocks actions, such as a commit hook or a command filter for agents, is a
control with failure modes of its own. Test what it does when its interpreter or script is missing,
when it times out, and when its input is unexpected, and choose deliberately whether each case lets
the action through (fail open) or blocks it (fail closed). Record the choice: a launcher that cannot
find its script and exits with the blocking code stops all work, while one that allows everything
when it fails protects nothing.

## Rules for changes and agents

- Preserve lint, type, coverage, contract, and test controls. A policy adjustment requires a reason separate
  from the functional change and explicit review; see [CI protection](ci.md).
- Respect architectural decisions; document alternatives and pending experiments before replacing
  them. Keep implementation, tests, and documentation consistent.
- Validate external data in adapters. Bound and justify `Any`, casts, `type: ignore`, and `noqa`; a
  difficult-to-type SDK does not justify disabling checks for an entire module.
- Justify production dependencies: need, existing alternative, maintenance, license, vulnerabilities,
  size, and transitive cost.
- Verify agent claims against sources and executed results. A code index is derived context; a plan or
  skill is not evidence of compliance.

## Dependency maintenance

Assign an owner and review versions monthly as a starting point; do so sooner for vulnerabilities,
end of support, or failures. Record whether to update, keep, or defer, with a reason and next
date/condition. Keep instructions in a single configuration.

Adopt a new or upgraded dependency version only after a minimum release age, which gives a broken
or malicious release time to be found and withdrawn. Fourteen days is a starting point for new
dependencies; routine updates can wait less. Exempt security fixes and record why. Package managers
and update tools can enforce the age, transitive dependencies included. After a conflict, regenerate
the lockfile instead of merging its text, and recheck branches that wait for a release age against
lockfile changes on their base.

Audit resolved dependencies with relevant extras/groups and delivery platforms. A Linux environment
may omit Windows-only packages: compare the inventory and lockfile before claiming full coverage.
Keep the tool, date, revision, inventory, and result; a failed query or pending warning is not an
approved audit.

Review content, history, and artifacts according to their exposure. When distributing, check licenses
and notices for transitive dependencies and binaries; verify provenance and hashes of downloaded
tools. Close updates with affected tests and artifact installation where appropriate, following
[validation](validation.md).

References, checked on 2026-10-16 against the claims they support:
[Ruff settings](https://docs.astral.sh/ruff/settings/),
[Ruff rule selection](https://docs.astral.sh/ruff/linter/#rule-selection),
[coverage](https://coverage.readthedocs.io/en/latest/config.html),
[pytest markers](https://docs.pytest.org/en/stable/how-to/mark.html),
[pytest strict configuration](https://docs.pytest.org/en/stable/reference/reference.html#confval-strict_config),
[checkJs](https://www.typescriptlang.org/tsconfig/checkJs.html).

Sources checked on 2026-10-17 against the claims they support:
[release age in pnpm](https://pnpm.io/settings/dependency-resolution),
[Dependabot cooldown](https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference);
and on 2026-10-19: [large-scale changes](https://abseil.io/resources/swe-book/html/ch22.html),
[frozen rules](https://www.archunit.org/userguide/html/000_Index.html).
