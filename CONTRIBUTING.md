# Contributing

## Editing

- Keep all maintained content in English, including skills, guides, comments, fixtures, and tool
  messages.
- Keep one explanation per rule. The guides under `skills/*/references/` explain rules,
  `criteria.md` lists checks that link to them, and `SKILL.md` holds the procedure. Update the
  source and link to it instead of repeating it.
- Write criteria as verifiable checks that name no specific tool. Tools appear only as optional
  examples in the guides.
- Criterion IDs are stable. Add new ones at the end of their area. To retire one, remove its row and
  record the ID in the [decision record](docs/decisions.md) so it is never reused.
- Keep `SKILL.md` under 500 lines, with references one level deep and links inside the skill
  directory.
- Distinguish requirements, recommendations, and examples. Check sources when changing a
  recommendation and record the date.
- Follow the [commit policy](skills/auditing-repositories/references/commits.md) for this
  repository too.

## Validation

Requires Python 3.12+ and Git, with no external Python packages:

```bash
python3 tools/check.py
# When changing workflows, shell scripts, or their validator:
bash tools/check_workflows.sh
# Before every push (requires network access):
bash tools/check_secrets.sh
# Check external links (requires network access):
python3 -m tools.check_links
```

The first command checks local links and heading anchors, JSON/TOML syntax, text hygiene, and
secret-like filenames. It also checks skill metadata, self-contained links, criterion IDs, and the
consistency of the evaluation cases, then runs the tests. Use inline links of the form
`[text](target)` and headings starting with `#`. Technical accuracy needs separate review, and
secrets inside file contents need the third command.

The second command validates GitHub Actions workflows and their shell code with actionlint and
ShellCheck, and the repository's shell scripts with ShellCheck, downloaded at pinned versions and
verified with SHA-256 hashes. It requires Linux x86_64 (WSL2 or Ubuntu), Bash, curl, tar/xz,
coreutils, and network access. CI runs the first two commands on every push and pull request.

The third command scans every commit of every local branch for secrets with Gitleaks, pinned and
verified the same way, with the same requirements, and prints each finding with its value redacted.
It runs before a push because a pushed branch is already public; a scan in CI would find a leak only
after publication. A finding that is a deliberate fake, such as a seeded evaluation defect, goes
into `.gitleaksignore` by fingerprint after review. Configuration files and inline `gitleaks:allow`
comments are not accepted, because they can hide a real leak.

The fourth command reports links that respond with 404 or 410 as broken. Other errors, blocked
access, and timeouts are reported as unverified, and the command fails in both cases. A valid
response does not show that the content is current. The `External links` workflow runs the check
monthly and on demand.

## Integration

`main` requires the `documentation` and `workflows` checks to pass on the exact commit, also for
administrators, and keeps a linear history without force pushes. Pull requests are optional. To
integrate directly, check every new commit on its own tree, push the commits to a branch, wait for
both checks to pass on that commit, and then fast-forward `main` to the same commit. CI checks only
the commit it receives; `tools/check_range.py` checks each commit under it without the repository's
history, as a later bisection or revert would meet it:

```bash
python3 -m tools.check_range origin/main..HEAD
bash tools/check_secrets.sh
git push origin HEAD:refs/heads/<branch>
# After both checks pass on that commit:
git push origin HEAD:main
```

GitHub rejects a commit that has no passing checks, so `main` only receives verified commits.
Delete the branch after integration.

## Evaluations

After changing a skill, `criteria.md`, or an evaluation case, run every case as described in
[evals/README.md](evals/README.md) and add the results to [evals/RESULTS.md](evals/RESULTS.md). A
change that lowers coverage or recall, or adds false positives, needs a stated reason.

When handing off work, describe the change, rationale, checks, results, and limitations.
