# Evaluation results

Each run records the date, the revisions of the skill, cases, and scorer, the agent and model, the
prepared case revisions, and the score. Scores come from `python3 -m tools.evals score`.

## 2026-10-16 — Run 1

- Skill `1f172b0` (unchanged through `b2e7c04`), cases `b2e7c04`, scored with `d3e61c6`.
- Agents: one fresh Claude Code general-purpose subagent per case, with the skill copied outside
  this repository so the expected findings were not readable. The model was inherited from the
  coordinating session (Opus 5.5); the subagents' model was not independently verified.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `8ca9f29`.

| Case | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 16 of 16 | CI-09 | 69 of 69 | 46 | 1 | 22 |
| typescript-cli | 13 of 13 | none | 69 of 69 | 40 | 5 | 24 |
| well-maintained | 2 of 2 | REPO-01 | 69 of 69 | 8 | 26 | 35 |

Notes:

- The scorer first reported 24 typescript-cli IDs as uncovered because the report listed them as
  indented bullets. `d3e61c6` reads that form; the table uses the corrected score.
- REPO-01 in well-maintained was a correct finding: the case documented `python`, which stock
  Ubuntu does not provide. The same audit found an undocumented transliteration defect. Both were
  case errors, fixed in `80adb0a`.
- CI-09 in python-service exposed an ambiguous rule for criteria that depend on unreadable hosted
  settings, clarified in `d8876be`.
- Whether the audits left the prepared repositories unmodified was not checked in this run.

## 2026-10-16 — Run 2

- Skill `d8876be`, cases `80adb0a`, scored with `d3e61c6`.
- Agents: three new Claude Code general-purpose subagents with the same prompt and isolation as
  run 1. The model was inherited from the coordinating session (Opus 5.5) and not independently
  verified.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `6578802`.

| Case | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 16 of 16 | none | 69 of 69 | 39 | 1 | 29 |
| typescript-cli | 13 of 13 | none | 69 of 69 | 38 | 5 | 26 |
| well-maintained | 2 of 2 | none | 69 of 69 | 7 | 25 | 37 |

Notes:

- After each audit, `git status --porcelain --ignored` was empty and HEAD was unchanged in every
  prepared repository.
- CI-09 in python-service is now not applicable, citing the missing `merge_group` trigger.
- The audits also reported real defects that were not seeded: typescript-cli splits quoted CSV
  fields and overwrites its input by default (ARCH-02), and the well-maintained README still says
  accented Latin letters become their base letter, while the code drops letters such as Ł, Đ, Ø,
  and ß (REPO-06, confirmed with `unicodedata`). The well-maintained defect remains in the case;
  fixing it or adding it to `must_find` requires another run.
- Two runs of three cases measure these seeded defects only. They do not establish recall on real
  repositories or with other agents and models.

## 2026-10-16 — Runs 3 and 4 (v0.2 method)

- Skill `caf7f11` (risk-based sampling, priority rubric, reproduction of high findings), cases
  `80adb0a` (unchanged through `caf7f11`), scored with `1d968a6`.
- Agents: one fresh Claude Code general-purpose subagent per case and run, launched with the
  `opus` alias. Each reported `claude-opus-5-5`; the model is self-reported, not independently
  verified.
- The six planned Sonnet runs failed before starting: the local model alias configuration did not
  resolve to a Claude Sonnet model (HTTP 404, model_not_found). This round has no second model.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `6578802`.

| Case | Run | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable | High (reproduced) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 3 | 16 of 16 | none | 69 of 69 | 42 | 1 | 26 | 6 (4) |
| python-service | 4 | 16 of 16 | none | 69 of 69 | 38 | 2 | 29 | 4 (4) |
| typescript-cli | 3 | 13 of 13 | none | 69 of 69 | 36 | 6 | 27 | 5 (3) |
| typescript-cli | 4 | 13 of 13 | none | 69 of 69 | 37 | 5 | 27 | 7 (4) |
| well-maintained | 3 | 2 of 2 | none | 69 of 69 | 8 | 21 | 40 | 0 |
| well-maintained | 4 | 2 of 2 | REPO-01 (disputed) | 69 of 69 | 9 | 24 | 36 | 0 |

Run-to-run agreement from `python3 -m tools.evals compare`, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 1 and 2 (before the rubric) | 82 of 96 | 184 of 207 | 73 of 82 |
| 3 and 4 (with the rubric) | 80 of 90 | 187 of 207 | 71 of 80 |

Notes:

- The priority rubric did not measurably change priority agreement (89% in both pairs). Two runs
  per case are too few to show a small effect either way.
- Every high finding was marked; 15 of 22 were reproduced, the rest inferred.
- REPO-01 in run 4 is disputed rather than wrong: the case README does not say that commands run
  from the repository root or how the publishing tool obtains the package. The case needs that
  clarification; its expectation was not changed after seeing the result.
- The audits found more real, unseeded defects in the well-maintained case: failing tests outside
  the default discovery pattern are skipped silently, titles starting with `-` are parsed as
  options, and letters such as Ø and ß are dropped despite the README.
- Three audits left scratch copies under `/tmp`, and one ran a command in a scratch directory it
  had not created. The copies were removed after the runs. The skill needs a scratch-copy rule.
- The scorer first reported two IDs as uncovered in run 3 because one bullet listed two IDs;
  `1d968a6` fixed the parser, and the table uses the corrected scores.

## 2026-10-16 — Runs 5 and 6 (GLM 5.3)

- Skill `caf7f11`, cases `80adb0a`, scored with `1d968a6`.
- Agent: Claude Code 2.1.287 headless (`claude -p`) in WSL2, one fresh process per case and run,
  three at a time, with the maintainer's Z.ai settings. Allowed tools were Bash, Read, Grep, and
  Glob; Write, Edit, WebFetch, and WebSearch were disallowed, and the report was returned as the
  final message. The CLI's `modelUsage` metadata reported `glm-5.3[1m]` for every run, so the model
  is host-observed. No tool call was denied.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `6578802`.

| Case | Run | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable | High (reproduced) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 5 | 16 of 16 | none | 69 of 69 | 31 | 8 | 30 | 4 (2) |
| python-service | 6 | 16 of 16 | none | 69 of 69 | 31 | 5 | 33 | 2 (1) |
| typescript-cli | 5 | 13 of 13 | none | 69 of 69 | 33 | 10 | 26 | 3 (1) |
| typescript-cli | 6 | 13 of 13 | none | 69 of 69 | 34 | 7 | 28 | 3 (2) |
| well-maintained | 5 | 1 of 2 (missed CI-06) | none | 69 of 69 | 4 | 26 | 39 | 0 |
| well-maintained | 6 | 1 of 2 (missed CI-06) | none | 69 of 69 | 6 | 26 | 37 | 0 |

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 5 and 6 (GLM with GLM) | 62 of 77 | 184 of 207 | 46 of 62 |
| 3 and 5 (Opus with GLM) | 64 of 90 | 152 of 207 | 54 of 64 |

Notes:

- Both GLM runs missed CI-06 in well-maintained by marking it not applicable, citing the
  hosted-settings rule added in `d8876be`. That rule gives "no remote" as an example of a missing
  indication, but CI-06 applies whenever CI configuration exists; without a remote it is pending
  verification. Opus applied the rule correctly in all four of its runs. The rule needs to say that
  a criterion whose condition the repository shows stays applicable, and a new evaluation round
  must follow that change.
- GLM reported fewer findings than Opus in the service and CLI cases (31 to 34 against 36 to 42),
  reproduced 6 of 12 high findings, and agreed less with itself and with Opus on statuses and
  priorities.
- GLM had no false flags, left every prepared repository unchanged, and left no copies of the
  cases under `/tmp`.
