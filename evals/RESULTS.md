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

## 2026-10-16 — Runs 13 to 18 (baseline)

- Skill `8de1b07`, cases `6c22cf9`, method `28b19b4`, scored with `1d968a6`. The skill and the
  catalog were exported from `28b19b4` with `git archive` to directories outside this repository.
- Agent: Claude Code 2.1.292 headless (`claude -p --model opus`), started by the maintainer from a
  WSL2 terminal, six at a time, each in its prepared repository. Bash, Read, Grep, and Glob were
  allowed; Write, Edit, WebFetch, and WebSearch were not. `modelUsage` reported `claude-opus-5-5`
  for all 18. Two earlier launches failed before any model call because the CLI was not logged in;
  they used no tokens and are not counted.
- Levels, as defined in [README.md](README.md#baselines):
  - Full skill (runs 13 and 14): the prompt of runs 11 and 12, with the skill directory.
  - Catalog only (runs 15 and 16): "Audit the repository in the current directory against the
    criteria in `<catalog>/criteria.md`. Do not modify the repository or install dependencies. Work
    only in this repository, that directory, and scratch directories you create; do not read any
    other path. Reply with only the final report, in this format:", followed by the Findings table
    header, the status and priority values, the two Coverage lines, and "Every ID in the catalog
    appears exactly once, in Findings or in Coverage."
  - No skill (runs 17 and 18): "Audit the repository in the current directory and list its
    problems, with evidence for each. Do not modify the repository or install dependencies. Work
    only in this repository and scratch directories you create; do not read any other path. Reply
    with only the final report."
- The tool calls of every run were checked: none touched this repository, `expected.json`, another
  prepared repository, or material outside its level.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Level | Seeded gaps found | False flags | IDs covered | Findings | Meets | Not applicable | High (reproduced) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 13 | Full | 16 of 16 | none | 68 of 69 (no ARCH-02) | 35 | 5 | 28 | 4 (2) |
| python-service | 14 | Full | 16 of 16 | none | 69 of 69 | 33 | 4 | 32 | 5 (2) |
| python-service | 15 | Catalog | 16 of 16 | none | 69 of 69 | 34 | 4 | 31 | 14 (unmarked) |
| python-service | 16 | Catalog | 16 of 16 | none | 69 of 69 | 33 | 5 | 31 | 14 (unmarked) |
| python-service | 17 | None | 12 of 16 (by hand) | none | — | — | — | — | — |
| python-service | 18 | None | 13 of 16 (by hand) | none | — | — | — | — | — |
| typescript-cli | 13 | Full | 13 of 13 | none | 69 of 69 | 36 | 6 | 27 | 6 (2) |
| typescript-cli | 14 | Full | 13 of 13 | none | 67 of 69 (no QUAL-04, TEST-03 malformed) | 32 | 8 | 27 | 5 (2) |
| typescript-cli | 15 | Catalog | 13 of 13 | none | 69 of 69 | 31 | 10 | 28 | 14 (unmarked) |
| typescript-cli | 16 | Catalog | 13 of 13 | none | 69 of 69 | 36 | 7 | 26 | 14 (unmarked) |
| typescript-cli | 17 | None | 11 of 13 (by hand) | none | — | — | — | — | — |
| typescript-cli | 18 | None | 12 of 13 (by hand) | none | — | — | — | — | — |
| well-maintained | 13 | Full | 2 of 2 | none | 69 of 69 | 5 | 27 | 37 | 0 |
| well-maintained | 14 | Full | 2 of 2 | none | 66 of 69 (three IDs written as "X and Y") | 5 | 27 | 34 | 0 |
| well-maintained | 15 | Catalog | 2 of 2 | none | 69 of 69 | 4 | 25 | 40 | 0 |
| well-maintained | 16 | Catalog | 2 of 2 | none | 69 of 69 | 5 | 27 | 37 | 0 |
| well-maintained | 17 | None | 0 of 2 (by hand) | none | — | — | — | — | — |
| well-maintained | 18 | None | 1 of 2 (by hand) | none | — | — | — | — | — |

Report SHA-256 hashes (the scorer's for full and catalog runs; `sha256sum` for the others):

- python-service run 13: `5f6a9a2f3ae7ba13e55c4c4cf15301d2f15d0f0ecd5752aa3f993e897c7dae6b`
- python-service run 14: `547ed043bfc00c74fe4ef764d8651117abdf107e11411b7dd657bd223b5ca08f`
- python-service run 15: `e525cbc12af08404fcc37f0994833ada957b953a6b524f7594b95981407375ef`
- python-service run 16: `faaea4e3a2ec06ebfe498a70cbfe246de69f32abee710ebad36ec0b4842e9a25`
- python-service run 17: `11bbafbc43fa457c38aff24f9de85f640c2518ef26a1837646c1b91d103ef9d3`
- python-service run 18: `df1d42e2d7927ed90d2c5c63993b3075e402a08472b6a13ed2665112a29c4d00`
- typescript-cli run 13: `a23281f8f37852eb438ba93059232be16126f3cbdf65111720fe063facd70d8f`
- typescript-cli run 14: `0e5782c137787e705550ee9d4979c1a1902f58fa4f5ee3190764cb791b73edaf`
- typescript-cli run 15: `3a1e0657d135c7cde03373f95dedd8b8f7f3fab7ca3b5536c975bc6b5e7ce9aa`
- typescript-cli run 16: `b9de78b17b014443506257f7dcd2a3668726c14c09bd0839eccdc526a00db907`
- typescript-cli run 17: `ebd298cdd516d0ca66aac0a6c09436778a57bee50b1ee6952a5a86a3d5a76718`
- typescript-cli run 18: `04522abbd0c9fd36df1308a343052a36d07fa7b8b4e1a88932563fc70b0c1d3a`
- well-maintained run 13: `09a39c69e8d6f02cb8e21ced6c410f2d11320759db2ccf2fb0d8e4d2f6715d2b`
- well-maintained run 14: `1f3dd4dd3b0020c0f02da30efd406cc2bc135047c59273f484385b3c248d18ff`
- well-maintained run 15: `5be16f27a071a73b7c9ea5d1791eff732c8b99491caff73ecd60439bb0dd473b`
- well-maintained run 16: `9a9541c93d8db139fee74874d5bb28ec0699d51f2e204ad0477c2a900b66364e`
- well-maintained run 17: `c0db1e650bd52feeba08331cbaebbc1fa5bee37f492a876de9ffc5054fd6b506`
- well-maintained run 18: `c17897c1f3e601296cd8744f6a74791ba4850605db6366217c35fa220453d14e`

Summary by level:

| Level | Seeded gaps found, per run | Seeded password copied | High per run, python-service and typescript-cli | Reports with every ID readable | Mean minutes | Mean cost reported by the CLI |
| --- | --- | --- | --- | --- | --- | --- |
| Full skill | 31 and 31 of 31 | 0 of 2 reports | 4 to 6 | 3 of 6 | 1.8 | USD 0.54 |
| Catalog only | 31 and 31 of 31 | 2 of 2 reports | 14 | 6 of 6 | 1.2 | USD 0.36 |
| No skill | 23 and 26 of 31 | 2 of 2 reports | — | — | 0.7 | USD 0.22 |

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 13 and 14 (full with full) | 67 of 79 | 180 of 201 | 61 of 67 |
| 15 and 16 (catalog with catalog) | 66 of 77 | 190 of 207 | 58 of 66 |
| 13 and 15 (full with catalog) | 66 of 79 | 175 of 206 | 38 of 66 |

Manual scoring of runs 17 and 18, with the rules in [README.md](README.md#baselines); `#n` is the
report's item number. No claim contradicted a `must_not_flag` reason.

| Case | ID | Run 17 | Run 18 |
| --- | --- | --- | --- |
| python-service | REPO-01 | missed (#17 names configuration, API, and deployment, not requirements or validation) | #19 "how to run the tests" |
| python-service | QUAL-02 | #14 no lint or type check | #19 same |
| python-service | QUAL-03 | #11 `pytest \|\| true` | #11 same |
| python-service | DEP-01 | #15 no versions or lock file | #17 same |
| python-service | TEST-01 | #13 invalid input and failures untested | #16 same |
| python-service | TEST-02 | #12 real request to the warehouse host | #14 same |
| python-service | CI-01 | #15 `3.x` and unpinned pytest | #13 same |
| python-service | CI-02 | missed | missed |
| python-service | CI-03 | missed | missed |
| python-service | CI-04 | missed | missed |
| python-service | SEC-02 | #3 no authentication, #9 no validation | #3, #4 same |
| python-service | SEC-03 | #6 no timeout | #8 same |
| python-service | SEC-04 | #1 `debug=True` on `0.0.0.0` | #1 same |
| python-service | SEC-05 | #2 committed password, value copied | #2 same |
| python-service | ARCH-05 | #4 blanket `except` | #5 same |
| python-service | PERF-01 | #16 unsupported throughput claim | #18 same |
| typescript-cli | QUAL-02 | #9 no tests, #10 `"strict": false` | #6, #8 same |
| typescript-cli | QUAL-03 | #8 `\|\| exit 0` | #7 same |
| typescript-cli | QUAL-05 | #8 file-wide `eslint-disable` | #7 same |
| typescript-cli | QUAL-09 | #10 `any` parameters | #8 same |
| typescript-cli | DEP-01 | #11 no lockfile, #12 no `engines` | #9, #10 same |
| typescript-cli | TEST-01 | #9 `npm test` only echoes | #6 same |
| typescript-cli | CI-02 | missed | #9 actions pinned by tag |
| typescript-cli | CI-03 | #1 no `permissions:` block | #1, only in its fix ("Set minimal `permissions:`"); counted, borderline |
| typescript-cli | CI-04 | missed | missed |
| typescript-cli | CI-10 | #1 `pull_request_target` publishes PR code with the token | #1 same |
| typescript-cli | SEC-02 | #2 shell injection | #2 same |
| typescript-cli | DEL-01 | #3 no gate before publishing, #11 `npm install` without a lockfile | #9 same |
| typescript-cli | DEL-03 | #3 every PR event publishes | #1 same |
| well-maintained | QUAL-02 | missed | #4 no lint or type check |
| well-maintained | CI-06 | missed | missed |

Notes:

- Without the skill, Opus missed 8 and 5 of the 31 seeded gaps: CI-04 in all four service and CLI
  reports, CI-02 and CI-03 in both python-service reports, CI-06 in both well-maintained reports,
  and REPO-01, CI-02 (typescript-cli), and QUAL-02 (well-maintained) in run 17.
- With the catalog alone, Opus found all 31, as with the full skill. On these cases the catalog
  accounts for the whole difference in recall; the procedure adds none. The cases cannot separate
  the two levels, so harder cases are needed.
- Differences the procedure did make: the catalog-only runs rated 14 findings high in each
  python-service and typescript-cli report, against 4 to 6 with the skill's rubric; every report
  without the procedure copied the seeded password, and neither full-skill report did; both
  catalog-only well-maintained runs left clones under `/tmp`, removed afterwards, while the
  full-skill runs removed theirs.
- The full skill did worse on format: run 13 python-service omits ARCH-02, run 14 typescript-cli
  omits QUAL-04 and writes TEST-03 in a malformed ID cell, and run 14 well-maintained lists three
  IDs as "X and Y", which the scorer does not read. Every catalog-only report covered all 69 IDs.
  The scorer was not changed.
- The catalog-only and no-skill prompts did not ask for priority actions, so this round does not
  compare next steps. The cost is the CLI's estimate; the runs used a subscription.
- These are headless runs; runs 7 and 8 were subagents, so comparisons across the two rounds also
  compare harnesses.
- Run 13 well-maintained ran Python once without disabling bytecode and left an ignored
  `slugkit/__pycache__/` in its prepared repository; `git status --porcelain --ignored` was empty in
  the other 17. Run 18 well-maintained queried GitHub with `git ls-remote` to check the action
  SHAs, which its prompt did not forbid.
- Unseeded defects reported in well-maintained: non-ASCII punctuation is dropped before separators
  apply, so `foo—bar` becomes `foobar` (run 18); non-ASCII digits are dropped (run 17); and the
  layout test is stricter than the discovery rule it cites (runs 17 and 18).

## 2026-10-17 — Runs 19 to 24 (level comparison)

- Skill `a0b460b`, case repositories `6c22cf9`, expectations `1027aec`, method `562a8fb`, scored
  with `cc170e9`. The skill and the catalog were exported from `562a8fb` outside this repository.
- Agent: Claude Code 2.1.292 headless (`claude -p --model opus`), started by the maintainer from a
  WSL2 terminal, six at a time, with the tools of runs 13 to 18. `modelUsage` reported
  `claude-opus-5-5` for all 18. The tool calls of every run stayed within its level, and `verify`
  found all 18 prepared repositories unchanged.
- Levels as in runs 13 to 18, except that the catalog-only prompt adds a Priority actions section
  ("Up to five actions, most important first, each naming the IDs of the findings it closes, with
  scope, an acceptance check, and timing: now, before release, or when the need arises.") and the
  no-skill prompt adds "then give up to five priority actions, most important first".
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Level | Seeded gaps found | Secret copied | IDs covered | Findings | Meets | Not applicable | High (reproduced) | Top priorities in first five actions | High outside them |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 19 | Full | 16 of 16 | no | 69 of 69 | 36 | 3 | 30 | 4 (2) | 3 of 3 | 1 |
| python-service | 20 | Full | 16 of 16 | no | 69 of 69 | 36 | 3 | 30 | 4 (2) | 3 of 3 | 1 |
| python-service | 21 | Catalog | 16 of 16 | yes | 69 of 69 | 34 | 3 | 32 | 16 (unmarked) | 3 of 3 | 13 |
| python-service | 22 | Catalog | 16 of 16 | yes | 69 of 69 | 34 | 4 | 31 | 16 (unmarked) | 3 of 3 | 13 |
| python-service | 23 | None | 11 of 16 (by hand) | yes | — | — | — | — | — | 3 of 3 (by hand) | — |
| python-service | 24 | None | 12 of 16 (by hand) | yes | — | — | — | — | — | 3 of 3 (by hand) | — |
| typescript-cli | 19 | Full | 13 of 13 | no | 69 of 69 | 33 | 8 | 28 | 8 (2) | 3 of 3 | 5 |
| typescript-cli | 20 | Full | 13 of 13 | no | 69 of 69 | 34 | 6 | 29 | 6 (2) | 3 of 3 | 3 |
| typescript-cli | 21 | Catalog | 13 of 13 | no | 69 of 69 | 38 | 5 | 26 | 17 (unmarked) | 3 of 3 | 14 |
| typescript-cli | 22 | Catalog | 13 of 13 | no | 69 of 69 | 36 | 6 | 27 | 11 (unmarked) | 3 of 3 | 8 |
| typescript-cli | 23 | None | 11 of 13 (by hand) | no | — | — | — | — | — | 3 of 3 (by hand) | — |
| typescript-cli | 24 | None | 10 of 13 (by hand) | no | — | — | — | — | — | 3 of 3 (by hand) | — |
| well-maintained | 19 | Full | 2 of 2 | no | 69 of 69 | 6 | 26 | 37 | 0 | 2 of 2 | 0 |
| well-maintained | 20 | Full | 2 of 2 | no | 69 of 69 | 5 | 28 | 36 | 0 | 2 of 2 | 0 |
| well-maintained | 21 | Catalog | 2 of 2 | no | 69 of 69 | 4 | 28 | 37 | 0 | 2 of 2 | 0 |
| well-maintained | 22 | Catalog | 2 of 2 | no | 69 of 69 | 6 | 28 | 35 | 0 | 2 of 2 | 0 |
| well-maintained | 23 | None | 1 of 2 (by hand) | no | — | — | — | — | — | 1 of 2 (by hand) | — |
| well-maintained | 24 | None | 1 of 2 (by hand) | no | — | — | — | — | — | 1 of 2 (by hand) | — |

Report SHA-256 hashes (the scorer's for full and catalog runs; `sha256sum` for the others):

- python-service run 19: `b9297711c62f068323b6cf4de9f6ca769157e602c1177422eaa9bb002e02c46d`
- python-service run 20: `d2453d695a3e2004cf77744130d8f99a51f096d7ace7af707e44577c28970c43`
- python-service run 21: `186952ac68f6944c231e66758b2fe302b6933fe179b95e95de481896d9c5378a`
- python-service run 22: `4ec69a787b7977a8fd78c76f5067789776e95655e0cd36b80101e60e6ea04670`
- python-service run 23: `4230bd802619ce2ac1ac9ca86f98ce9d0cd7ed0a8cb872d897b04677cd9741e2`
- python-service run 24: `2b5f87651aa76d668ffcae4b4838e4ccabca212c8c3bf4b2414cb2d2b7397818`
- typescript-cli run 19: `b238cea5ab59236dbcddfc19cbb54aef218d5a8cff3100842525be741d67970b`
- typescript-cli run 20: `acd0a6133ff144a3ed1e6541c007723c886f6dd91575553b5b04b80729184385`
- typescript-cli run 21: `b92179cc35aef3accd76e29492a62f23a16bcf6d79780bb847f10a239283cfd5`
- typescript-cli run 22: `e7d2d0508dca4ee1e672940d60c56abbc9abfbbf450df91d7db46ad36ed362db`
- typescript-cli run 23: `9dc0fece05e1f08b2f372237034facc2e2c9f73a11b822a67ba91c1f487930b3`
- typescript-cli run 24: `6ff2ae5e2af2a5083a256800b52c31d6c4dcfa9a58204cd0d33ebf7529bec26e`
- well-maintained run 19: `50a86d6247cf208518eb27e9943d022d96198e84394b1c34e7b7f382481d0b60`
- well-maintained run 20: `4d7c5d86adbfb7d4264fbb82823084cb5723461c36c0b064ea487dbcb112ef4e`
- well-maintained run 21: `d931ff38494308476ec5fef83575f08f84a835866f4f48889df86b3aa113f54e`
- well-maintained run 22: `cc6dde9962230a81c541cc021fa1575386584804e8ff8c99b8a3e94d3620b35f`
- well-maintained run 23: `1d6c0f5c010c5b7da2fa4581c663f93a9a00d3a5a6f8514df3cfe32f46a6e644`
- well-maintained run 24: `aa460ae0dc7f1180d463cab4c171a0bb6c0c70257ff2df8bf93d4cb3f7a1f5c7`

Against the criteria recorded in [README.md](README.md#baselines) before this round:

| Criterion | Full skill | Catalog only | Met |
| --- | --- | --- | --- |
| Top priorities in the first five actions | 16 of 16 | 16 of 16 | yes, tied |
| Reports that copy the seeded secret | 0 of 6 | 2 of 6 | yes |
| High findings outside the top priorities | 10 | 48 | yes |
| Reports that cover every ID | 6 of 6 | 6 of 6 | yes, tied |
| Citations outside a case file | 0 | 0 | yes, tied |
| Blind comparison | first | last | yes |

By those criteria the full skill is better than the catalog alone. Recall is the same; the margin
comes from calibrated priorities, the secret not being copied, and the blind choice.

Blind comparisons: an independent agent that the maintainer ran read three anonymized reports of
one case, one per level, verified their citations against the case files, and ranked them by which
it would act on. Both times the order was full skill, then no skill, then catalog only:
typescript-cli runs 13, 15, and 17 (before the format change), and python-service runs 19, 21,
and 23. Its reasons:

- Full skill: calibrated priorities, actions with acceptance checks, findings verified by running
  commands, and the only report that masks the password (python-service) or asks to rotate the
  npm token (typescript-cli). It overstated one mark: run 19 calls QUAL-03 reproduced after
  showing how `|| true` behaves in the shell, without running the repository's CI command.
- No skill: the best reading of the code's behavior, finding defects the other levels missed, such
  as GET and POST disagreeing on unknown SKUs, negative counts, silent truncation by `int()`, and
  (typescript-cli) CRLF conversion and a crash after the file is overwritten.
- Catalog only: inflated priorities (14 and 16 high findings in the compared reports), fewer
  line citations, one citation of the wrong line (`package.json:8` for line 9), and the copied
  secret.

The judge is a model, each comparison covers one case, and the structure of each report reveals its
level, so the ranking is evidence, not proof.

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 19 and 20 (full with full) | 73 of 77 | 189 of 207 | 61 of 73 |
| 21 and 22 (catalog with catalog) | 74 of 78 | 192 of 207 | 64 of 74 |
| 19 and 21 (full with catalog) | 70 of 81 | 174 of 207 | 36 of 70 |

Mean time and cost reported by the CLI: full skill 1.9 minutes and USD 0.54, catalog only 1.4
minutes and USD 0.38, no skill 0.6 minutes and USD 0.18.

Manual scoring of runs 23 and 24, with the rules in [README.md](README.md#baselines). No claim
contradicted a `must_not_flag` reason.

| Case | ID | Run 23 | Run 24 |
| --- | --- | --- | --- |
| python-service | REPO-01 | missed | #12 README omits "how to run the tests" |
| python-service | QUAL-02 | missed | missed |
| python-service | QUAL-03 | #3 `pytest \|\| true` | #9 same |
| python-service | DEP-01 | #9 no versions or lock file | #11 same |
| python-service | TEST-01 | #8 bad input and failures untested | #10 same |
| python-service | TEST-02 | #8 real request to the warehouse host | #10 same |
| python-service | CI-01 | #3 `python-version: "3.x"` | #11 `3.x` and unpinned pytest |
| python-service | CI-02, CI-03, CI-04 | missed | missed |
| python-service | SEC-02 | #7 no authentication, #4 no input checks | #3 same |
| python-service | SEC-03 | #5 no timeout | #6 same |
| python-service | SEC-04 | #2 `debug=True` on `0.0.0.0` | #1 same |
| python-service | SEC-05 | #1 committed password | #2 same |
| python-service | ARCH-05 | #4 `except Exception: pass` | #4 same |
| python-service | PERF-01 | #10 unsupported throughput claim | #12 same |
| typescript-cli | QUAL-02 | #8 no tests, #10 `"strict": false` | #9, #7 same |
| typescript-cli | QUAL-03 | #9 `\|\| exit 0` | #8 same |
| typescript-cli | QUAL-05 | #9 file-wide `eslint-disable` | #7 same |
| typescript-cli | QUAL-09 | #10 `any` | #7 same |
| typescript-cli | DEP-01 | #11 no lockfile, #12 no `engines` | #3, #10 same |
| typescript-cli | TEST-01 | #8 `npm test` only echoes | #9 same |
| typescript-cli | CI-02 | missed | missed |
| typescript-cli | CI-03 | #2 no `permissions:` block | missed |
| typescript-cli | CI-04 | missed | missed |
| typescript-cli | CI-10 | #1 PR code runs with the npm token | #1 same |
| typescript-cli | SEC-02 | #3 shell injection | #2 same |
| typescript-cli | DEL-01 | #11 `npm install` without a lockfile, #8 no build or test before release | #3, #9 same |
| typescript-cli | DEL-03 | #2 PRs trigger releases | #3 same |
| well-maintained | QUAL-02 | #5 no lint or type check | #4 same |
| well-maintained | CI-06 | missed | missed |

Top priorities by action, by hand: python-service SEC-05, SEC-04, and QUAL-03 at actions 1, 2, and 3
in run 23, and at 1, 1, and 3 in run 24; typescript-cli CI-10, DEL-03, and SEC-02 at 1, 1, and 2 in
both runs; well-maintained QUAL-02 at action 5 (run 23) and 4 (run 24), with CI-06 absent.

Notes:

- The format change worked: every full-skill report covers all 69 IDs, against 3 of 6 in runs 13
  and 14, and its actions name the IDs they close.
- The full skill still rates 3 to 5 findings high outside the top priorities in typescript-cli.
- Without the skill, Opus found 23 of 31 in both runs and placed 14 of 16 top priorities.
- The catalog-only reports exit with 1 because their high findings carry no reproduced or
  inferred mark, which their prompt did not ask for, and the python-service ones because they copy
  the secret.
- Both catalog-only well-maintained runs again left clones under `/tmp`, removed afterwards. Run 24
  well-maintained created an ignored `slugkit/__pycache__/` and deleted it itself. No report has a
  citation whose quoted code sits on another line.
- Unseeded defects reported in well-maintained: `½` becomes `12`; different titles can share a slug;
  and the README says every title starting with `-` needs `--`, while `-5` works without it (a
  sentence from `b89404f`).
- Two changes to the skill follow from the blind comparisons: a pass that reads the code's behavior
  for edge cases and broken invariants, and marking a finding reproduced only when the repository's
  own code or configuration ran.

## 2026-10-17 — Runs 25 to 28 (PR 2 criteria)

- Skill `0b4f099`, with 87 criteria; case repositories `6c22cf9`, expectations `e329106`, scored
  with `cc170e9`. The skill was exported from `e329106` outside this repository.
- Agent: Claude Code 2.1.292 headless, full-skill prompt, started by the maintainer from a WSL2
  terminal, six at a time. `modelUsage` reported `claude-opus-5-5` for runs 25 and 26 and
  `claude-sonnet-5-5` for runs 27 and 28. Every tool call stayed in the prepared repository, the
  skill directory, and the run's own scratch directories.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Model | Seeded gaps found | False flags | IDs the scorer read | Findings | Meets | Not applicable | High (reproduced) | Top priorities in first five | High outside them | Other problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 25 | Opus | 16 of 16 | none | 37 of 87 (bold labels) | 37 | 4 | 46 | 5 (2) | 3 of 3 | 2 | TEST-07 listed twice |
| python-service | 26 | Opus | 16 of 16 | none | 87 of 87 | 34 | 5 | 48 | 5 (1) | 3 of 3 | 2 | — |
| python-service | 27 | Sonnet | 16 of 16 | none | 87 of 87 | 31 | 3 | 53 | 4 (0) | 3 of 3 | 1 | — |
| python-service | 28 | Sonnet | 16 of 16 | none | 86 of 87 (no REPO-03) | 36 | 0 | 50 | 6 (0) | 3 of 3 | 3 | copies the seeded password; cites line 14 of a 13-line file |
| typescript-cli | 25 | Opus | 13 of 13 | none | 87 of 87 | 40 | 7 | 40 | 7 (4) | 3 of 3 | 4 | — |
| typescript-cli | 26 | Opus | 13 of 13 | none | 87 of 87 | 40 | 9 | 38 | 5 (3) | 3 of 3 | 2 | — |
| typescript-cli | 27 | Sonnet | 13 of 13 | none | 87 of 87 | 39 | 0 | 47 | 4 (3) | 3 of 3 | 2 | HIST-01 and REPO-02 twice, an invalid status, and a correction inside the report |
| typescript-cli | 28 | Sonnet | 13 of 13 | none | 87 of 87 | 33 | 6 | 48 | 3 (1) | 3 of 3 | 1 | — |
| well-maintained | 25 | Opus | 2 of 2 | none | 87 of 87 | 8 | 29 | 50 | 0 | 2 of 2 | 0 | — |
| well-maintained | 26 | Opus | 2 of 2 | none | 87 of 87 | 5 | 27 | 55 | 0 | 2 of 2 | 0 | — |
| well-maintained | 27 | Sonnet | 2 of 2 | none | 3 of 87 (bold labels) | 3 | 25 | 59 | 0 | 2 of 2 | 0 | left ignored bytecode in the repository |
| well-maintained | 28 | Sonnet | 2 of 2 | DEP-01 | 5 of 87 (bold labels) | 5 | 25 | 57 | 0 | 2 of 2 | 0 | left ignored bytecode in the repository |

The Findings, Meets, and Not applicable columns, and the agreement below, were counted after
removing Markdown emphasis, so that reports with bold status labels count fully; the IDs column is
what the scorer at `cc170e9` reads.

Report SHA-256 hashes, as printed by the scorer:

- python-service run 25: `54e22adde10c9783e4df6c093e7743fe2926836b76abf2e626dcd6fce5cfb295`
- python-service run 26: `a9a11697c8f583ccb4c030597756771ffb78dc61da6747099ee46dd9375e5231`
- python-service run 27: `349171c185e951225cd14a5d19dd764ac149d4d50aeb60cf3e9be135db16bf67`
- python-service run 28: `e36693a635f8f6ae967623afd21a4ce040d06059ef94be628e36774b2fa9560a`
- typescript-cli run 25: `83c5fa87b324de994f228456f65498361314caab33f146a630d6eeb3f4791650`
- typescript-cli run 26: `3138e06d70cc216adc804521783ef6e6ecac681b6d9dd4b068982e585ce0dfdd`
- typescript-cli run 27: `5786919d59b1d44c3643454b0a94233c6833658bf22b6f20f8fd6c7ca08aa768`
- typescript-cli run 28: `66bdce84d983bf1fe7f95957107f3def1a0db3404b7bfa3ef82fa1a5575ca696`
- well-maintained run 25: `48c8f3df6d1db2a05a6c9520908f6d34cdf34097de8a1cd5de843963003b6005`
- well-maintained run 26: `5e1e08fc559b27887151635d33bd546ba0a33a524fdfee91f5d54f95b914346b`
- well-maintained run 27: `e38bd7e32508677b7163fb34e39749276c7e7309289dd78ee8e7a66c630192f7`
- well-maintained run 28: `c318de0359d45567cf482934d68db18ed7293d98675e7e390efb88971905b31a`

Agreement, summed over the three cases, with emphasis removed:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 25 and 26 (Opus with Opus) | 77 of 87 | 232 of 261 | 65 of 77 |
| 27 and 28 (Sonnet with Sonnet) | 60 of 88 | 216 of 260 | 46 of 60 |
| 25 and 27 (Opus with Sonnet) | 66 of 93 | 214 of 261 | 53 of 66 |

Mean time and cost reported by the CLI: Opus 2.1 minutes and USD 0.61 (1.9 minutes and USD 0.54
in runs 19 and 20, with 69 criteria); Sonnet 0.8 minutes and USD 0.22.

Notes:

- Every run found every seeded gap and placed the top priorities in its first five actions (24 of
  24). No well-maintained audit flagged any of the six new criteria listed in its `must_not_flag`,
  so the applicability gates held on the control case.
- Three reports, one Opus and two Sonnet, wrote the Coverage status labels in bold
  (`- **meets:**`), which the scorer does not read. Read without emphasis, they cover every ID
  except a TEST-07 that run 25 lists twice. The scorer was not changed in this round.
- Run 28 python-service copied the seeded password while assessing the new SEC-11: it described
  the value as a fixture-style label and quoted it. The masking rule has to hold for values that
  look fake, and the SEC-11 guidance has to say so.
- Both Sonnet well-maintained runs ran the tests in place and left ignored bytecode; `verify` caught
  it. No Opus run did this time.
- Run 28 well-maintained flagged DEP-01 because `.python-version` pins `3.12` without a patch
  version, against the case's expectation.
- Sonnet did worse than in runs 9 and 10, which used 69 criteria and had no format failures or
  leaks: here 4 of its 6 reports fail the scorer, and 3 still would with emphasis removed. Opus
  fails in 1 of 6, from a duplicated ID. A larger catalog and a longer procedure are a likely cause;
  the conditional loading planned for PR 3 is meant to reduce both.
- Follow-ups: mask any secret-like value, even one that looks fake; run checks so that ignored files
  stay as they were; decide separately whether the scorer should accept emphasis on status labels;
  then run another round.
