# Small, verifiable commits

Apply this policy to new commits from the time it is adopted. The limits are initial project
values, not a universal standard. Changing them requires a justified decision. Each commit
serves one purpose, includes the necessary tests and documentation, and leaves a valid revision.
Do not split code and tests to meet a number or mix unrelated tasks.

## Limits

| Measure per commit | Usual maximum |
| --- | --- |
| Changed files | 15 |
| Lines added + deleted | 500 |
| Subject characters, including prefix | 72 |

Count against the parent; compare the initial commit with an empty tree. A renamed file counts
once using Git rename detection at 50%. A replaced line counts as one deletion and one insertion;
do not use the net total. Include code, tests, documentation, lockfiles, and generated files.
Do not exclude entire directories from the calculation. Binaries and submodules count as files;
report bytes and reference changes separately because `--numstat` does not represent their size
as reviewable lines.

Review staged content with `git diff --cached --stat` and
`git diff --cached --numstat --find-renames=50%`. These commands show metrics;
by themselves they do not enforce the limits. For an existing commit:

```sh
git show --format= --stat --numstat --find-renames=50% <sha>
```

If a limit is exceeded, split by responsibility while keeping each commit valid. For an
indivisible operation (bootstrap, regeneration, lockfile update, or mechanical migration),
record `Commit-Exception: <reason and reference>` in the body, including the counts,
affected paths, and why splitting would make review worse. The exception must be explicitly
reviewed before integration; the trailer alone is not approval. Large binaries also need an
explicit budget and reason. The subject format has no exception.

## Naming

Always use `type: description` or `type(scope): description`, with a space after `:`.
Allowed types: `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`,
`style`, and `revert`. Use lowercase for the type; the optional scope uses lowercase letters,
numbers, and hyphens to identify a module. The description briefly states the action, is not
empty, and has no trailing period.

```text
feat(api): add task pagination
fix(runtime): avoid retries after uncertain effects
docs: clarify installation requirements
```

Separate the body from the subject with a blank line. Explain the reason, compatibility, and
evidence when they are not obvious. For incompatible changes, add `BREAKING CHANGE: <impact>`
in the footer and explain the migration; keep the two requested subject formats, without `!`.
Reverts use `revert(scope): description` and reference the reverted SHA in the body.
This policy constrains [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/).

## Integration and enforcement

Prefer linear history. Review every retained commit and the final integration result; a squash
must also respect the limits, even when its source commits were small. For a large change,
integrate several coherent commits instead of one giant squash. Resolve temporary
`fixup!`/`squash!` messages before integration. In a stack, every commit passes the gates, not
only the head: a broken intermediate revision surfaces later in bisection or a partial revert.

This policy is enforced by review until the project automates it. To make it mandatory,
connect the same validator to hooks and CI: subject, files, lines, and exceptions. CI must review
new commits against the adoption baseline and the final integration commit, and be a required
branch check. Check rejection of invalid names, oversized commits, and unreviewed exceptions;
hooks and PR titles alone do not guarantee compliant history.

## Earlier commits

- Local and unshared: they may be renamed with amend/reword or split with interactive rebase.
  Renaming does not fix size; an oversized commit needs splitting.
- Published on a working branch: rewrite only with authorized scope and coordination with its
  users. Check remote state and, if the rewrite is to be published, use a lease with the expected
  remote reference and SHA; never use a blind force push.
- Integrated into a shared branch or associated with a release: preserve by default.
  Apply the policy going forward; history aesthetics do not justify breaking references.

Before an authorized rewrite: identify the branch/range and consumers, preserve a backup
reference, and isolate uncommitted changes. Afterward: validate every resulting commit,
compare the final tree with the original (it must be identical if only reorganized), preserve
authorship, and document old/new SHAs where references exist. Hashes change and signatures
and review links may become invalid; do not move release tags automatically.

References: [rebasing and splitting commits](https://git-scm.com/docs/git-rebase),
[push with an explicit lease](https://git-scm.com/docs/git-push).
The links in this guide were checked on 2026-10-16 against the claims they support.
