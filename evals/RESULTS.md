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

## 2026-10-16 — Runs 7 to 12 (after the batch A fixes)

- Skill `ab605f0`, cases `b89404f`, scored with `1d968a6`. The skill was exported from `b89404f`
  with `git archive` to a directory outside this repository.
- Prompt: "Use the auditing-repositories skill at `<skill>`: read its SKILL.md and follow it to
  audit the repository at `<repo>`. Work only in that repository, the skill directory, and scratch
  directories you create; do not read any other path." Subagents were asked to write the report
  outside the prepared repository; GLM was asked to reply with it.
- Runs 7 and 8: new Claude Code general-purpose subagents launched with the `opus` alias. Runs 9
  and 10: the same with the `sonnet` alias. Every response in each transcript records
  `claude-opus-5-5` or `claude-sonnet-5-5`, so the model is host-observed. The harness refused
  report files from subagents, so each report is the subagent's final message from `## Context`
  to the end, unedited.
- Runs 11 and 12: GLM 5.3 through Claude Code 2.1.287 headless, as in runs 5 and 6, with
  `stream-json` output so that every tool call could be inspected. The maintainer started them from
  a WSL2 terminal because the session's permission classifier blocked launching headless agents.
  `modelUsage` reported `glm-5.3[1m]` for every run. One Bash call was denied (run 11
  well-maintained, a write into its own scratch clone), and the audit continued.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `8ef9ef4`.

| Case | Run | Model | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable | High (reproduced) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 7 | Opus | 16 of 16 | none | 69 of 69 | 40 | 1 | 28 | 5 (3) |
| python-service | 8 | Opus | 16 of 16 | none | 69 of 69 | 40 | 1 | 28 | 5 (2, 3 unmarked) |
| python-service | 9 | Sonnet | 16 of 16 | none | 69 of 69 | 33 | 4 | 32 | 5 (4) |
| python-service | 10 | Sonnet | 16 of 16 | none | 69 of 69 | 36 | 3 | 30 | 3 (2) |
| python-service | 11 | GLM | 16 of 16 | none | 69 of 69 | 30 | 9 | 30 | 4 (1) |
| python-service | 12 | GLM | 16 of 16 | none | 69 of 69 | 31 | 7 | 31 | 4 (2) |
| typescript-cli | 7 | Opus | 13 of 13 | none | 69 of 69 | 40 | 5 | 24 | 7 (3) |
| typescript-cli | 8 | Opus | 13 of 13 | none | 69 of 69 | 37 | 7 | 25 | 6 (3) |
| typescript-cli | 9 | Sonnet | 13 of 13 | none | 69 of 69 | 36 | 6 | 27 | 5 (5) |
| typescript-cli | 10 | Sonnet | 13 of 13 | none | 69 of 69 | 36 | 5 | 28 | 4 (2) |
| typescript-cli | 11 | GLM | 13 of 13 | none | 68 of 69 (no DEP-03) | 30 | 11 | 27 | 1 (1) |
| typescript-cli | 12 | GLM | 13 of 13 | none | 69 of 69 | 35 | 7 | 27 | 4 (2) |
| well-maintained | 7 | Opus | 2 of 2 | none | 69 of 69 | 9 | 26 | 34 | 0 |
| well-maintained | 8 | Opus | 2 of 2 | none | 69 of 69 | 7 | 28 | 34 | 0 |
| well-maintained | 9 | Sonnet | 2 of 2 | none | 69 of 69 | 9 | 25 | 35 | 0 |
| well-maintained | 10 | Sonnet | 2 of 2 | none | 69 of 69 | 7 | 23 | 39 | 0 |
| well-maintained | 11 | GLM | 2 of 2 | none | 69 of 69 | 9 | 29 | 31 | 0 |
| well-maintained | 12 | GLM | 2 of 2 | none | 69 of 69 | 9 | 27 | 33 | 0 |

Report SHA-256 hashes printed by the scorer:

- python-service run 7: `788a8622c3c0dcc418a4747247e61b66da542f80bd9bd83693c6bdeb581677ee`
- python-service run 8: `f48bc8eb5100258dc6dea94eea457f70cab26b6ec92899464d6940c341c343cc`
- python-service run 9: `98de2849efa56c3eb04b648f4338057c7fb057dea9560359e9fd8a6677cb00da`
- python-service run 10: `a1bcfa8122f7d3861f891f1713aa69b8c842c60dbc3e947fac87607b0ccb948a`
- python-service run 11: `567557fd036921b5bacaa128b83588b96d49fcdceae9f79b520b63c4cca2001e`
- python-service run 12: `980fa67b36600bd8bfc5819a77cbe00b0c7df5d315290b50e09e6c6f1b7f6640`
- typescript-cli run 7: `86fec22870d577415b4a75ff7d8b5c2544a7027fb7f067816f7cb2291e5dd008`
- typescript-cli run 8: `792715819f4b207e6de6b6a16629b1c3b5cf3e00eae9a65251509b5bb0426ae0`
- typescript-cli run 9: `d101f6dacbd94428464fa28b30c879e23a7502d466f6c516205e12336bba6fe1`
- typescript-cli run 10: `0a3f6a3c69e6aaaed6e94811c089b0450f122f5ef35a1b67d344c3b1e8cd222c`
- typescript-cli run 11: `a0a838f0ee7367f6c318f8d5ed7c56a9711597ae5c541953eb8078521822ad48`
- typescript-cli run 12: `e6dafa9be7f1b65ba7e8593debc9b08e73b3f88bb3b3ac6d604db5b3a443b0a9`
- well-maintained run 7: `838b993646a29661b88259336cd7d1e23105619770e9f32240b4b7668c4c66f2`
- well-maintained run 8: `a6d86cb186c1bab2968c46e9833ad6c6d34c73f0eeed35a166d0a851f70d755d`
- well-maintained run 9: `e8ca61e84cd5e8b036b0912be5de3af6e0ce42bf2b9ef8c7badf8d7e33ea5eb9`
- well-maintained run 10: `1dfb07e02accb52d05ba046defefd486c93e190d9fccf64649511be1c6d88c1f`
- well-maintained run 11: `11ecd1625b63d146331a2b22ac2c90d705b8e1704331449d51b28237f18e4cfe`
- well-maintained run 12: `f712192acaf7d483a4ae95b87e43040a4017242ca9e0f0bf45d295bb1ce82914`

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 7 and 8 (Opus with Opus) | 81 of 92 | 185 of 207 | 75 of 81 |
| 9 and 10 (Sonnet with Sonnet) | 73 of 84 | 186 of 207 | 67 of 73 |
| 11 and 12 (GLM with GLM) | 63 of 81 | 169 of 206 | 50 of 63 |
| 7 and 9 (Opus with Sonnet) | 77 of 90 | 185 of 207 | 65 of 77 |
| 7 and 11 (Opus with GLM) | 67 of 91 | 145 of 206 | 46 of 67 |

Notes:

- All six well-maintained audits found CI-06, including both GLM runs, which missed it in runs 5
  and 6. None flagged REPO-01, which was disputed in run 4.
- Every run found every seeded gap, and none flagged a `must_not_flag` criterion. Two runs fail
  the scorer on format: run 8 python-service wrote three high findings as `Inferred (Flask is not
  installed, so this was not run):`, which does not start with `Inferred:`, and run 11
  typescript-cli omitted DEP-03. The scorer was not changed after seeing these results.
- Agreement within Opus and within Sonnet is close to runs 3 and 4. GLM agreed less with itself
  than in runs 5 and 6 (169 of 206 statuses against 184 of 207) and less with Opus.
- These runs do not measure what the skill adds. Every recorded run used it, and the seeded
  defects are common ones that a model may find without it. A baseline without the skill, and
  with the catalog only, is planned.
- `b89404f` introduced an error in the well-maintained case. Its README says that a test file is
  never skipped because of its name, but discovery skips modules whose names are not identifiers,
  such as `test-cli.py`, and subdirectories without `__init__.py` (confirmed in a scratch copy).
  The README also omits that compatibility characters expand (`ﬁ` becomes `fi`), so a
  200-character title can produce an 800-character slug. Runs 7, 8, and 9 reported the first as
  QUAL-04, and runs 7 and 8 reported the second as REPO-06. Neither ID is expected either way, so
  scores are unaffected; the case needs a fix and another round.
- Every audit named and deleted its scratch directories. No copy of a case remained under `/tmp`
  or the session's scratchpad, and `git status --porcelain --ignored` was empty in all 18
  prepared repositories. However, subagents of one session share its scratchpad, and 8 audits
  stored their scratch path in a file with a fixed name: runs 8 and 9 python-service, 9 and 10
  well-maintained, and 10 python-service and typescript-cli in the shared scratchpad, and runs 11
  and 12 typescript-cli under `/tmp`. Two pairs used the same file at the same time.
- Incident: in run 10 typescript-cli, run 10 python-service deleted the shared path file. A `cd`
  into the missing directory then failed without stopping the command, which ran in the
  subagent's starting directory, the working tree of this repository. It extracted the
  typescript-cli case there and ran `npm run lint` with a stub linter. The audit noticed,
  compared each file with the case, restored `README.md` with `git checkout`, and removed the
  files it had added. Afterwards the working tree matched HEAD with no extra files, directories,
  hooks, or configuration changes, and the transcripts show that no audit read `expected.json`.
  Follow-up: run evaluations from a working directory outside this repository, and extend the
  scratch rule so that a command stops when its scratch directory is missing and the path is not
  kept in a shared file.
- Three typescript-cli audits (runs 8, 9, and 10) wrote 11 npm debug logs to the user's npm log
  directory before redirecting npm's paths. The logs contain only scratch paths and were not
  removed.
