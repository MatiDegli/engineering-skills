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

## 2026-10-17 — Runs 29 to 32 (masking, ignored files, emphasis)

- Skill `1a2df3a`, case repositories `6c22cf9`, expectations `e329106`, scored with `15b7a15`. The
  skill was exported from `15b7a15` outside this repository.
- Agent and prompt as in runs 25 to 28: `modelUsage` reported `claude-opus-5-5` for runs 29 and 30
  and `claude-sonnet-5-5` for runs 31 and 32. Every tool call stayed in the allowed paths, `verify`
  found all 12 prepared repositories unchanged, and no copy was left under `/tmp`.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Model | Seeded gaps found | False flags | IDs the scorer read | Findings | Meets | Not applicable | High (reproduced) | Top priorities in first five | High outside them | Other problems |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 29 | Opus | 16 of 16 | none | 87 of 87 | 35 | 4 | 48 | 5 (1) | 3 of 3 | 2 | — |
| python-service | 30 | Opus | 16 of 16 | none | 39 of 87 (grouped bullets) | 36 | 3 | 48 | 4 (2) | 3 of 3 | 1 | — |
| python-service | 31 | Sonnet | 16 of 16 | none | 84 of 87 (no QUAL-04, ARCH-01, ARCH-06) | 42 | 0 | 42 | 6 (0) | 3 of 3 | 3 | — |
| python-service | 32 | Sonnet | 16 of 16 | none | 86 of 87 (no REPO-03) | 39 | 0 | 47 | 5 (0) | 3 of 3 | 2 | — |
| typescript-cli | 29 | Opus | 13 of 13 | none | 87 of 87 | 40 | 6 | 41 | 6 (2) | 3 of 3 | 3 | — |
| typescript-cli | 30 | Opus | 13 of 13 | none | 87 of 87 | 40 | 7 | 40 | 6 (3) | 3 of 3 | 3 | — |
| typescript-cli | 31 | Sonnet | 13 of 13 | none | 87 of 87 | 37 | 5 | 45 | 4 (2) | 3 of 3 | 2 | — |
| typescript-cli | 32 | Sonnet | 13 of 13 | none | 87 of 87 | 36 | 6 | 45 | 4 (1) | 3 of 3 | 1 | — |
| well-maintained | 29 | Opus | 2 of 2 | none | 87 of 87 | 7 | 27 | 53 | 0 | 2 of 2 | 0 | — |
| well-maintained | 30 | Opus | 2 of 2 | none | 87 of 87 | 6 | 30 | 51 | 0 | 2 of 2 | 0 | — |
| well-maintained | 31 | Sonnet | 2 of 2 | DEP-01 | 52 of 87 (several IDs per bullet) | 5 | 22 | 60 | 0 | 2 of 2 | 0 | — |
| well-maintained | 32 | Sonnet | 2 of 2 | none | 87 of 87 | 6 | 25 | 56 | 0 | 2 of 2 | 0 | — |

The Findings, Meets, and Not applicable columns and the agreement below use a broader reading of
indented Coverage bullets: a leading label such as "Agents and tooling:" is dropped, reasons in
parentheses are removed, and every remaining ID counts. The IDs column is what the scorer reads.

Report SHA-256 hashes, as printed by the scorer:

- python-service run 29: `3c37725ed6cde3954fccbb407ed94f3b43d18e288cf23157c003bd88d0cb1e01`
- python-service run 30: `d499ddc6021aaf3b0d499ca150e3381e9970ea790a917abcb50ce7dbb4b1a2f6`
- python-service run 31: `666b59ec0738d93fd1343a896444d0aa402599906707fb70c08bdd1713633627`
- python-service run 32: `67f5478ea95dffaafdd0797297e4bd0650d3d639d524690233d3f9402d054d54`
- typescript-cli run 29: `0cc642264b78cff8edb8416f2e36f9f79476cc641ed0ec0204c6a0b4975f3599`
- typescript-cli run 30: `d9270db618763f81f2ffe8b64b1abcab054a585283956bdf7899c18cd6a9f6d7`
- typescript-cli run 31: `76ef583eb0288cb8f9e8ca6098ac52c71351edebc666555ee10f93927af42b87`
- typescript-cli run 32: `35bc9a63cc139e7aaab3cc93395c05e58ac7afae86bc695d711a37843e7ebbbe`
- well-maintained run 29: `5d88d163000019f586135a94e2314834331f48ed19d127ced818834d31d49b19`
- well-maintained run 30: `434d270d102e9ba177031bd2009fe4db0d3d01b47aea367ba1633d71641a128e`
- well-maintained run 31: `471a6e411af5eecc2bce7450642f221b442a402bd13bfacf231b033ab5ef2aa0`
- well-maintained run 32: `72488414d1b0dba947e803d2c8a2064b47772e68d77a00cc8801f29014e7729d`

Agreement, summed over the three cases, with the broader reading:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 29 and 30 (Opus with Opus) | 78 of 86 | 242 of 261 | 71 of 78 |
| 31 and 32 (Sonnet with Sonnet) | 72 of 93 | 218 of 257 | 60 of 72 |
| 29 and 31 (Opus with Sonnet) | 67 of 99 | 212 of 258 | 49 of 67 |

Mean time and cost reported by the CLI: Opus 2.2 minutes and USD 0.58; Sonnet 0.8 minutes and
USD 0.20.

Notes:

- Both fixes worked: no report copied the seeded password (one Sonnet report did in runs 25 to
  28), and no audit left ignored files in its repository (both Sonnet control runs did).
- Every run again found every seeded gap and placed the top priorities in its first five actions,
  and no control case audit flagged a new criterion listed in its `must_not_flag`.
- Two reports used Coverage layouts the scorer does not read: run 30 groups not-applicable IDs
  under area labels, and run 31 well-maintained puts several "ID (reason)" entries in one indented
  bullet. Read more broadly, both cover all 87 IDs. The scorer keeps counting only the IDs that open
  an indented bullet, so that IDs inside reasons are not counted; the Coverage format, with
  area-level lines, is planned for PR 3.
- Sonnet omitted IDs in both python-service reports: QUAL-04, ARCH-01, and ARCH-06 in run 31, and
  REPO-03 in run 32, which run 28 also omitted. Opus covered every ID in substance.
- Run 31 well-maintained flagged DEP-01 for the minor-version runtime pin, as run 28 did. Sonnet
  reads the criterion as asking for a patch pin; the expectation and Opus do not.
- Scorer failures by model: Opus 1 of 6 (format only), Sonnet 3 of 6 (two with missing IDs, one with
  a false flag and an unread layout).

## 2026-10-17 — Runs 33 to 36 (criteria loaded by area)

- Skill `6cd1e15`, with 74 core criteria and 13 in the agents, delivery, and operations area
  files; case repositories `6c22cf9`, expectations `e329106`, scored with `9846c6f`. The skill was
  exported from `ba29912` outside this repository.
- Agent and prompt as in runs 29 to 32: `modelUsage` reported `claude-opus-5-5` for runs 33 and 34
  and `claude-sonnet-5-5` for runs 35 and 36. Every tool call stayed in the allowed paths, `verify`
  found all 12 prepared repositories unchanged, and no audit copy was left under `/tmp`. Each run's
  stream was kept, so the files every audit read are known.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Model | Seeded gaps found | False flags | IDs the scorer read | Findings | Meets | Not applicable | High (reproduced) | Top priorities in first five | High outside them |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 33 | Opus | 16 of 16 | none | 87 of 87 | 34 | 5 | 48 | 5 (2) | 3 of 3 | 2 |
| python-service | 34 | Opus | 16 of 16 | none | 87 of 87 | 33 | 5 | 49 | 5 (2) | 3 of 3 | 2 |
| python-service | 35 | Sonnet | 16 of 16 | none | 74 of 87 (area wildcards outside the list) | 31 | 4 | 52 | 4 (0) | 3 of 3 | 1 |
| python-service | 36 | Sonnet | 16 of 16 | none | 74 of 87 (a separate "not-applicable areas" line) | 30 | 4 | 53 | 4 (0) | 3 of 3 | 1 |
| typescript-cli | 33 | Opus | 13 of 13 | none | 87 of 87 | 39 | 7 | 41 | 7 (3) | 3 of 3 | 4 |
| typescript-cli | 34 | Opus | 13 of 13 | none | 87 of 87 | 39 | 8 | 40 | 7 (3) | 3 of 3 | 4 |
| typescript-cli | 35 | Sonnet | 13 of 13 | none | 84 of 87 (no REPO-03, STRUCT-01, DEL-04) | 36 | 0 | 48 | 5 (0) | 3 of 3 | 2 |
| typescript-cli | 36 | Sonnet | 13 of 13 | none | 87 of 87 | 35 | 6 | 46 | 4 (1) | 3 of 3 | 1 |
| well-maintained | 33 | Opus | 2 of 2 | none | 87 of 87 | 8 | 26 | 53 | 0 | 2 of 2 | 0 |
| well-maintained | 34 | Opus | 2 of 2 | none | 87 of 87 | 6 | 26 | 55 | 0 | 2 of 2 | 0 |
| well-maintained | 35 | Sonnet | 2 of 2 | ARCH-05 | 87 of 87 | 4 | 21 | 62 | 0 | 2 of 2 | 0 |
| well-maintained | 36 | Sonnet | 2 of 2 | DEP-01 | 87 of 87 | 6 | 23 | 58 | 0 | 2 of 2 | 0 |

The Findings, Meets, and Not applicable columns and the agreement below also count area wildcards
that runs 35 and 36 wrote outside the not-applicable line.

Report SHA-256 hashes, as printed by the scorer:

- python-service run 33: `854196de4a28b83956e13ba57169dcdae8305d232680fb12c344dbbeba77a863`
- python-service run 34: `8074445870812885b4aa5ac0d9dfd64250604699edc940756309ccf0181fc1df`
- python-service run 35: `5bdec3830b684ed09c436eaa1b22960d55add298e00bb6efa2d01f2935ddafe3`
- python-service run 36: `c2fc1709e0de1e916fddede8420cde87e993392192f865057509b0b081ab809b`
- typescript-cli run 33: `7a096e0a4bebb31c1e03b34226ea86afc89ac781b20a68a9ae97620237b762e2`
- typescript-cli run 34: `afbe6901b2415f195f17be3c51b3a2a7b7b13b10fbcdc686879d6a320192c3a5`
- typescript-cli run 35: `2beaa79a78c82a680020303175a4072cf139b132f0ec512045f831ece3e3186c`
- typescript-cli run 36: `58ccb3666cbe01f3b7941992024fa384f160416ece850c2e74cd2a27b60dde03`
- well-maintained run 33: `db9f3809df21731345f689624c0dd88e1107bdbb11fe15d2dbf7f64fa6b91313`
- well-maintained run 34: `c8d4e02d76fe647c9724de0bb1de5f7bcfb62d67c879e56b672bdb6c13c15e3a`
- well-maintained run 35: `113d9238b25c66058259fc24ac526bb18ac68c33b0a839f61aed48eee786f614`
- well-maintained run 36: `e64ec934b16deed759fdadc67f5cf2d00089b64b6620a73fd8d7d2bf420c98ae`

Effect of loading by area, against runs 29 to 32 with the same models and cases:

| Measure | Runs 29 to 32 | Runs 33 to 36 |
| --- | --- | --- |
| Mean report length, Opus | 15.2 KB, 95 lines | 14.6 KB, 88 lines |
| Mean report length, Sonnet | 13.1 KB, 90 lines | 12.0 KB, 84 lines |
| Mean time and cost reported by the CLI, Opus | 2.2 minutes, USD 0.58 | 2.0 minutes, USD 0.55 |
| Mean time and cost reported by the CLI, Sonnet | 0.8 minutes, USD 0.20 | 0.9 minutes, USD 0.20 |
| Reports that pass the scorer, Opus | 5 of 6 | 6 of 6 |
| Reports that pass the scorer, Sonnet | 3 of 6 | 1 of 6 |

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 33 and 34 (Opus with Opus) | 75 of 84 | 241 of 261 | 67 of 75 |
| 35 and 36 (Sonnet with Sonnet) | 61 of 81 | 229 of 258 | 45 of 61 |
| 33 and 35 (Opus with Sonnet) | 63 of 89 | 211 of 258 | 53 of 63 |

Notes:

- Guides are now read by context. Eleven of the twelve audits read `criteria.md`, at most one area
  file, and at most `standard.md`; one Opus audit read seven guides, `standard.md` included. No
  audit opened the agents area, which no case needs. Subagents in runs 7 to 10 read all ten guides
  every time; the headless streams of later rounds before this one were not kept, so that
  comparison crosses harnesses.
- The cost fell by about 5% for Opus and not measurably for Sonnet: most of an audit's cost comes
  from reading the repository and running commands, not from the guides.
- Opus passed the scorer in all six reports, the first time since the PR 2 criteria.
- Both Sonnet python-service reports closed the three areas correctly but outside the format: run
  35 as bullets after the not-applicable line, and run 36 on its own "not-applicable areas" line.
  Read that way, both cover every ID.
- Sonnet run 35 typescript-cli omitted REPO-03, STRUCT-01, and DEL-04; Sonnet has now omitted
  REPO-03 in three of its last six python-service and typescript-cli reports.
- Run 35 well-maintained flagged ARCH-05 because letters without an ASCII form are dropped
  silently, although the README documents it and a test pins it. The new behavior step, which asks
  to look for silent changes to data, does not say that documented and tested behavior is not a
  defect. Run 36 flagged DEP-01 for the minor-version runtime pin, as Sonnet did in runs 28 and 31.
- Every run found every seeded gap and placed the top priorities in its first five actions, and no
  control case audit flagged an area criterion listed in its `must_not_flag`.
- Follow-ups: give area wildcards their own Coverage line and teach the scorer to read it; say in
  the behavior step that documented, tested behavior is not a defect; clarify in DEP-01 whether a
  supported minor runtime version counts as pinned.

## 2026-10-17 — Runs 37 to 40 (areas line, behavior and DEP-01 clarified)

- Skill `38bb20f`, case repositories `6c22cf9`, expectations `e329106`, scored with `18a8209`. The
  skill was exported from `38bb20f` outside this repository.
- Agent and prompt as in runs 33 to 36: `modelUsage` reported `claude-opus-5-5` for runs 37 and 38
  and `claude-sonnet-5-5` for runs 39 and 40. Every tool call stayed in the allowed paths, `verify`
  found all 12 prepared repositories unchanged, no audit copy was left under `/tmp`, and every
  stream was kept.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`.

| Case | Run | Model | Seeded gaps found | False flags | IDs the scorer read | Findings | Meets | Not applicable | High (reproduced) | Top priorities in first five | High outside them |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| python-service | 37 | Opus | 16 of 16 | none | 87 of 87 | 34 | 3 | 50 | 5 (2) | 3 of 3 | 2 |
| python-service | 38 | Opus | 16 of 16 | none | 87 of 87 | 33 | 5 | 49 | 6 (2) | 3 of 3 | 3 |
| python-service | 39 | Sonnet | 16 of 16 | none | 87 of 87 | 31 | 5 | 51 | 3 (0) | 3 of 3 | 1 |
| python-service | 40 | Sonnet | 16 of 16 | none | 87 of 87 | 30 | 6 | 51 | 4 (0) | 3 of 3 | 2 |
| typescript-cli | 37 | Opus | 13 of 13 | none | 87 of 87 | 38 | 7 | 42 | 7 (3) | 3 of 3 | 4 |
| typescript-cli | 38 | Opus | 13 of 13 | none | 87 of 87 | 38 | 6 | 43 | 5 (3) | 3 of 3 | 3 |
| typescript-cli | 39 | Sonnet | 13 of 13 | none | 86 of 87 (DEL-04 as "DEL-04: not-applicable") | 32 | 6 | 48 | 4 (1) | 3 of 3 | 1 |
| typescript-cli | 40 | Sonnet | 13 of 13 | none | 86 of 87 (no DEL-04; PERF-01 twice) | 39 | 1 | 46 | 4 (0) | 3 of 3 | 1 |
| well-maintained | 37 | Opus | 2 of 2 | none | 87 of 87 | 7 | 24 | 56 | 0 | 2 of 2 | 0 |
| well-maintained | 38 | Opus | 2 of 2 | none | 87 of 87 | 6 | 31 | 50 | 0 | 2 of 2 | 0 |
| well-maintained | 39 | Sonnet | 2 of 2 | none | 87 of 87 | 5 | 24 | 58 | 0 | 2 of 2 | 0 |
| well-maintained | 40 | Sonnet | 2 of 2 | none | 87 of 87 | 5 | 24 | 58 | 0 | 2 of 2 | 0 |

Report SHA-256 hashes, as printed by the scorer:

- python-service run 37: `33abb66cd0131d285553d485888e0e5a2d5715252d3e9895342e68bc547fad81`
- python-service run 38: `582803515eb875d85400d41762b42aacedaa14c6b499aff754eb7c683001ec6a`
- python-service run 39: `b2f66096d3ecc0cf8feb1cf95dc30ae9cef1a54beb1925b42e53e0ecd7d2882f`
- python-service run 40: `afc69119393b49df52629f1bc10f31e45502740ad55127bbc9226bc7ab5f1009`
- typescript-cli run 37: `53cff5383687906d08df40eca1341b844ce2704062e567a88ce90e3eb96b55f9`
- typescript-cli run 38: `7db6b1939183c4494bb9522636d4eb0b29d5472f7bc69da977f824dada37d871`
- typescript-cli run 39: `a35fc3a31f1fc63587b1a92a4b77176b75c1d1826585a2e51d27992ba3c34972`
- typescript-cli run 40: `ac22575838d0a3a84b6e437ac34da912053d62017f151d1f035e42fd172be91a`
- well-maintained run 37: `1a835f87225bb7b81f5e0fcd5df49116c2ff3b9ec240b56af55150df8df2adf4`
- well-maintained run 38: `e5790484d9d0c1d3fb2844044c2fce778b6b6a13f454b6b29aaeb8d344b4c2d6`
- well-maintained run 39: `745dcf8846ff4ac6fdf687291f6bd147708f263ef692b0e8c64cc361fb8e8d92`
- well-maintained run 40: `cb6971cf4a493e3ad9b443964e06011912cafaafea07ff2ddeaa940bfbf758bd`

Agreement, summed over the three cases:

| Runs | Flagged overlap | Status agreement | Priority agreement |
| --- | --- | --- | --- |
| 37 and 38 (Opus with Opus) | 77 of 79 | 247 of 261 | 63 of 77 |
| 39 and 40 (Sonnet with Sonnet) | 63 of 79 | 228 of 260 | 55 of 63 |
| 37 and 39 (Opus with Sonnet) | 67 of 80 | 234 of 260 | 50 of 67 |

Mean time and cost reported by the CLI: Opus 2.0 minutes and USD 0.55; Sonnet 0.9 minutes and
USD 0.20, as in runs 33 to 36.

Notes:

- Reports that pass the scorer: Opus 6 of 6, as in runs 33 to 36; Sonnet 4 of 6, against 1 of 6.
  Both Sonnet python-service reports used the "not-applicable areas" line, and no control case
  audit flagged ARCH-05 or DEP-01.
- Both remaining failures concern DEL-04 in typescript-cli, which Sonnet also omitted in run 35:
  run 39 wrote it as a bullet of its own, "DEL-04: not-applicable", which the scorer does not
  read, and justified it with security level 1 although the package is published to npm; run 40
  omitted it and listed PERF-01 both in Findings, as not-applicable, and in Coverage.
- Every run found every seeded gap and placed the top priorities in its first five actions, and no
  control case audit flagged a criterion listed in its `must_not_flag`.
- Opus agreed with itself on 77 of 79 flagged IDs, the highest overlap recorded.

## 2026-10-17 — Runs 41 to 46 (PR 4 cases, three models)

- Skill `38bb20f`, unchanged since runs 37 to 40; cases `389d098`, with the new agent-workflow,
  orders-service, and reserved go-ratelimiter cases; scored with `18a8209`. The skill was exported
  from `389d098` outside this repository.
- Agent and prompt as in runs 37 to 40, with three models: `modelUsage` reported `claude-opus-5-5`
  for runs 41 and 42, `claude-sonnet-5-5` for runs 43 and 44, and `claude-haiku-4-5-20251001` for
  runs 45 and 46. The `haiku` alias resolved to Haiku 4.5, not to the current Haiku. Every tool call
  stayed in the allowed paths, and every stream was kept.
- Prepared revisions: python-service `c67d66d`, typescript-cli `7f27a08`, well-maintained `5780341`,
  agent-workflow `c25b5a5`, orders-service `b6034f9`, go-ratelimiter `43224ac`.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 41 | Opus | 16 of 16 | no | 3 of 3 | unmarked high 1 |
| python-service | 42 | Opus | 16 of 16 | yes | 3 of 3 | — |
| python-service | 43 | Sonnet | 16 of 16 | no | 3 of 3 | uncovered 1 |
| python-service | 44 | Sonnet | 16 of 16 | no | 3 of 3 | duplicated 1 |
| python-service | 45 | Haiku 4.5 | 13 of 16 (missed CI-04, SEC-03, TEST-01) | no | 2 of 3 | secret copied, unmarked high 3, uncovered 16, duplicated 23 |
| python-service | 46 | Haiku 4.5 | 13 of 16 (missed CI-03, QUAL-02, SEC-03) | no | 3 of 3 | secret copied, unmarked high 3, uncovered 9 |
| typescript-cli | 41 | Opus | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 42 | Opus | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 43 | Sonnet | 13 of 13 | no | 3 of 3 | uncovered 1 |
| typescript-cli | 44 | Sonnet | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 45 | Haiku 4.5 | 10 of 13 (missed DEL-01, DEL-03, QUAL-05) | no | 2 of 3 | unmarked high 7, uncovered 22 |
| typescript-cli | 46 | Haiku 4.5 | 8 of 13 (missed CI-03, CI-04, QUAL-05, QUAL-09, SEC-02) | no | 2 of 3 | unmarked high 4, uncovered 37, duplicated 1 |
| well-maintained | 41 | Opus | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 42 | Opus | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 43 | Sonnet | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 44 | Sonnet | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 45 | Haiku 4.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 46 | Haiku 4.5 | 2 of 2 | no | 1 of 2 | uncovered 4, duplicated 1 |
| agent-workflow | 41 | Opus | 6 of 6 | no | 3 of 3 | uncovered 1 |
| agent-workflow | 42 | Opus | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 43 | Sonnet | 6 of 6 | no | 3 of 3 | duplicated 1 |
| agent-workflow | 44 | Sonnet | 6 of 6 | no | 3 of 3 | bad citations 2 |
| agent-workflow | 45 | Haiku 4.5 | 4 of 6 (missed AGENT-03, TEST-08) | no | 3 of 3 | unmarked high 1, uncovered 6 |
| agent-workflow | 46 | Haiku 4.5 | 2 of 6 (missed AGENT-02, AGENT-03, AGENT-04, TEST-08) | no | 2 of 3 | unmarked high 1, uncovered 32, duplicated 8 |
| orders-service | 41 | Opus | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 42 | Opus | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 43 | Sonnet | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 44 | Sonnet | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 45 | Haiku 4.5 | 9 of 9 | no | 1 of 3 | secret copied, unmarked high 13, uncovered 5, duplicated 34 |
| orders-service | 46 | Haiku 4.5 | 4 of 9 (missed OPS-02, OPS-04, QUAL-06, SEC-11, SEC-12) | no | 1 of 3 | unmarked high 2, uncovered 31, duplicated 7 |
| go-ratelimiter | 41 | Opus | 4 of 4 | yes | — | — |
| go-ratelimiter | 42 | Opus | 4 of 4 | yes | — | — |
| go-ratelimiter | 43 | Sonnet | 4 of 4 | no | — | bad citations 4 |
| go-ratelimiter | 44 | Sonnet | 4 of 4 | no | — | bad citations 1, uncovered 1 |
| go-ratelimiter | 45 | Haiku 4.5 | 3 of 4 (missed TEST-08) | no | — | unmarked high 3, uncovered 7, duplicated 1 |
| go-ratelimiter | 46 | Haiku 4.5 | 2 of 4 (missed QUAL-02, TEST-08) | no | — | uncovered 27, duplicated 1 |

The Problems column counts the scorer's failures other than missed gaps: IDs it could not read
(uncovered), IDs listed twice, high findings without a reproduced or inferred mark, copied secrets,
and citations outside a file.

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five |
| --- | --- | --- | --- |
| Opus | 100 of 100 | 10 of 12 | 26 of 28 |
| Sonnet | 100 of 100 | 5 of 12 | 28 of 28 |
| Haiku 4.5 | 72 of 100 | 1 of 12 | 19 of 28 |

Report SHA-256 hashes, as printed by the scorer:

- python-service run 41: `5fa0d3e25d79b4ce35768d7993d232769e8a2244a8c12c9f97ababd15899a423`
- python-service run 42: `ec951bc503078dafe61e950c0eb053c30e19d95794ee020e744644afa20da0d7`
- python-service run 43: `798448a10531f2d907991e69f39e34d72f42a5d0c2b49223defef25ea4b03105`
- python-service run 44: `6add0431ee590eada0cf66c4bd7afad02c6fcf76b2c40257815c27fbe9b6b50b`
- python-service run 45: `e2e105b8f839b54e1086092654f26eb0e6d9e11e9291a0dea88846848899f450`
- python-service run 46: `b2b033c673960fdd12673e149c4e6e67f944dfae4d9b3455c70a6f6d0eee8f69`
- typescript-cli run 41: `49c80831e303c1786f4e9ee61d712663f0247879287363a015ef34adf3b56fd6`
- typescript-cli run 42: `53084a033ae0d7831ff395a69981e985229622dbc98c5286bc5a86208c5b1392`
- typescript-cli run 43: `7699be30a88e91d005ad0640d76b038c7030cbef534e99c98cddbbe8f2cf2c19`
- typescript-cli run 44: `f51e5606926902e8a7ef83294fa751c138295e972dee92b830901be6867fa660`
- typescript-cli run 45: `9284295d0c9b77f74c8f515dfb1e16272619caa8688c08f07abe0eb4921f839e`
- typescript-cli run 46: `785f5b5402ffe48c539af1eb83a383ea7977d72cee1ee0da9d33a9c113379e02`
- well-maintained run 41: `b0a3af0711c81c48e9a827cd0ef39c5f49b18de3027cf2c3ff8d0d42a3adc848`
- well-maintained run 42: `79a46359e633a961382fbf4aa6c2a15f86df0f97ab4cbff92281a5115b3fedce`
- well-maintained run 43: `3f92d4c8065e6bcc1a04c5a16749f4729410a3aa2bb1f8de53a796e0665584fe`
- well-maintained run 44: `59b97bbdf477c8ab43fdb0652e7231d1b597991f34409ab70cda6dc1aafe3ed2`
- well-maintained run 45: `1259649ec092c84c4f8560ea06e9e37e440cc2ca69efc314377f0b72664a78db`
- well-maintained run 46: `6796ac6e4bd030af938a00d2ddbb6a1d5b896cbd58bad1e5c405dd6dd7fbd729`
- agent-workflow run 41: `565935acecf20eda6a750edd8123e6a924badede3b6f462bdff213bcc48dc996`
- agent-workflow run 42: `a73e2c1013f7da558cb0ea0b211b7d90c8c19b12cfa6271058253e4510d25b6a`
- agent-workflow run 43: `77f47f1c68c4967a96d0e892e1020e95ed916b61428b3dd09011a12badc5e860`
- agent-workflow run 44: `082d532789febd2a9e99c7b35009684ff1b13ac8c5ac2b4b0aa11dbd0c77dd5a`
- agent-workflow run 45: `f3ff909f09d1daed033d610d550ad6b3b1b18c9ec39aa0530dd8d8433e64d0fb`
- agent-workflow run 46: `c477d19718c0fa1af0bf60d867753df5aba0058e988daa2b4efbb04697210ad9`
- orders-service run 41: `5934dd35cb35bf5be90e98ab86cda12c66eec6b0e353cf78df17d251b96eb17b`
- orders-service run 42: `1db2a7084e944fe5f49925c4bb388c947c9743e1f42a1287240d61ab170aa980`
- orders-service run 43: `ad886e6dfbacad290dd2252a9d8ce10d92b6309f4e1cf904c0df64646cf96afd`
- orders-service run 44: `dff07bbfcc74eabeb5436275371c33c8d62279967573ba58b4f75328b9e68ab9`
- orders-service run 45: `6ae9f1e952fb3684e52f89c44813958b1f26c1688c255dd4bcc4dc34efd83ded`
- orders-service run 46: `c571d2a0f6cc027d45e5347ea03614cee5186d879cec70e3717ae4284869bbf1`
- go-ratelimiter run 41: `daa15728611566e2bc176bb5bd544ed42c12da9661b2b15a083a527de726c9a9`
- go-ratelimiter run 42: `3e6793198bef21023ed28c2bb277f780ad89868cb740cc88ab667d4ecb279b0b`
- go-ratelimiter run 43: `c82035a0cd8e506befae9aabba0990d7fa815cf03c40e8f373818a272c839dae`
- go-ratelimiter run 44: `5144e6eca36fb84e8fd2b179d4fdead125727d3177e3420d531ef267a8d8ff4b`
- go-ratelimiter run 45: `37fa4c4cc915e2d6c44aef38d1c7c5f0ea4bd3d2bb1e6f505e9aa5490e8c94e5`
- go-ratelimiter run 46: `50a46447e3a33db58937952e6360abc04ebb395e6e08b5765f5face4d6b6608a`

Mean time and cost reported by the CLI: Opus 2.4 minutes and USD 0.60; Sonnet 1.2 minutes and USD
0.23; Haiku 4.5 2.2 minutes and USD 0.23, with three to five times as many tool calls as Opus.

Notes:

- Opus and Sonnet found every seeded gap in all six cases, including the three new ones and the
  reserved Go case. No report flagged a criterion listed in `must_not_flag`.
- Neither Opus run placed OPS-02, the missing database backups, in its first five actions on
  orders-service; both Sonnet runs did. Opus ranked other operational and security work first.
- Sonnet cited lines beyond the end of a file in three reports of the new cases, for example
  `limiter.go:61` in a 40-line file and `README.md:39` in a 26-line one. The fabricated lines
  appeared in the Go case and in agent-workflow; Opus had none.
- Sonnet again omitted REPO-03 once and DEL-04 once, as in earlier rounds.
- Haiku 4.5 found 72 of 100 seeded gaps and passed the scorer once in 12 reports. Of its 28 missed
  gaps, 7 do not appear in the report at all, about 4 were found but listed under a status line
  instead of the Findings table, and the rest were judged wrongly: marked not applicable, met, or
  even listed as strengths, such as the agent brief template. Its problem is judgment more than
  format.
- Haiku 4.5 copied the seeded secret in three reports, including the high-entropy fake key of
  orders-service; left Python bytecode in four prepared repositories, two of them untracked rather
  than ignored; and one run wrote its notes to a fixed-name file, `/tmp/audit_scratch.txt`, removed
  afterwards. The skill's safety rules held for Opus and Sonnet.
- The reserved go-ratelimiter case is recorded like the others; by its definition, these results
  do not change the skill.

## 2026-10-17 — Runs 47 to 50 (cited line numbers, Haiku 5.5)

- Skill `8b2a2c6`, which takes cited line numbers from output that shows them and has `high`
  findings quote the code they cite; cases `389d098`, unchanged; scored with `fb5eaac`. The skill
  was exported from `8b2a2c6` outside this repository.
- Agent: Claude Code 2.1.299, headless, with the prompt of runs 41 to 46. Runs now name full model
  IDs and load only user settings, with hooks off, so an audited repository's own agent settings
  never load; the cases have none, so this does not change their runs. `modelUsage` reported
  `claude-opus-5-5` for run 47, `claude-sonnet-5-5` for runs 48 and 49, and `claude-haiku-5-5` for
  run 50. Claude Code 2.1.292 did not recognize `claude-haiku-5-5`.
- A first launch of the round failed before any tool call: the stored login had expired, and the
  parallel runs raced to refresh it. The round script now makes one short call per model, one at a
  time, before the parallel runs, and retries a run whose login refresh fails. Every stream was
  kept, outside this repository.
- Prepared revisions as in runs 41 to 46.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 47 | Opus | 16 of 16 | yes | 3 of 3 | — |
| python-service | 48 | Sonnet | 16 of 16 | yes | 3 of 3 | — |
| python-service | 49 | Sonnet | 16 of 16 | yes | 3 of 3 | — |
| python-service | 50 | Haiku 5.5 | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 47 | Opus | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 48 | Sonnet | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 49 | Sonnet | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 50 | Haiku 5.5 | 13 of 13 | no | 3 of 3 | false flag TOOL-01 |
| well-maintained | 47 | Opus | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 48 | Sonnet | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 49 | Sonnet | 2 of 2 | no | 2 of 2 | false flag CI-04 |
| well-maintained | 50 | Haiku 5.5 | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| agent-workflow | 47 | Opus | 6 of 6 | no | 3 of 3 | uncovered 1 |
| agent-workflow | 48 | Sonnet | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 49 | Sonnet | 6 of 6 | no | 3 of 3 | bad citations 2 |
| agent-workflow | 50 | Haiku 5.5 | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 47 | Opus | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 48 | Sonnet | 9 of 9 | no | 3 of 3 | uncovered 2, duplicated 1, false flag CI-03 |
| orders-service | 49 | Sonnet | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 50 | Haiku 5.5 | 9 of 9 | yes | 2 of 3 | — |
| go-ratelimiter | 47 | Opus | 3 of 4 (missed TEST-08) | no | — | — |
| go-ratelimiter | 48 | Sonnet | 4 of 4 | no | — | duplicated 1, bad citations 1 |
| go-ratelimiter | 49 | Sonnet | 4 of 4 | no | — | bad citations 3 |
| go-ratelimiter | 50 | Haiku 5.5 | 4 of 4 | yes | — | — |

The Problems column counts the scorer's failures other than missed gaps, as in runs 41 to 46.

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five |
| --- | --- | --- | --- |
| Opus | 49 of 50 | 4 of 6 | 13 of 14 |
| Sonnet | 100 of 100 | 7 of 12 | 28 of 28 |
| Haiku 5.5 | 50 of 50 | 4 of 6 | 13 of 14 |

Report SHA-256 hashes, as printed by the scorer:

- python-service run 47: `1561e34a4daf55c3ff0b2ec1975ed1a8c6a5ebe8bc8f39909501994607e55f78`
- python-service run 48: `b5b2bee97405bbb62b502a6231d73124282f18228a460cd1931f37e332d07e81`
- python-service run 49: `138131c740a12b01ff1bfa2a1c32a999bad0fcaa70d14cdc779a1c876cfdd1da`
- python-service run 50: `1014a5d65f698c872c1a4cc18dc52e50a8e90901d4ee7ecb907381177b8aa850`
- typescript-cli run 47: `02a042870a9056ba6f264ec2ca40dc906fff2babb99bc4860d54009b9bda3530`
- typescript-cli run 48: `a5227a68524030ddcd3e4450fb503ad8baecd6ed4f973d144a00c5f1b4243b30`
- typescript-cli run 49: `2a4cf7865997424209de6df103328377c0b5e380a609a1473c93e8441e3f052d`
- typescript-cli run 50: `23e06af9e0e804e72f06236158132b8f97a32f886fa7bfe860025a95526887a3`
- well-maintained run 47: `de6811fdf92508cb00bb825d0183d672384eb2cfef5b9fcc44506e6091ffc04a`
- well-maintained run 48: `2818d390a80302271ef6e585da43a585b2cf04457efe32db55cdc0f9378adb4f`
- well-maintained run 49: `054ce8b853511d0763b10e2accec22d08ca5921b44b562394caa794d6303d484`
- well-maintained run 50: `3e3cce0fd96ef674e69386fd4d2d47104821e83af44f938853cca5e55d5027c1`
- agent-workflow run 47: `8f10413e12e023cd391838a5e3aa9836e9caba4b53fdeb7e55829cfa5930a8ff`
- agent-workflow run 48: `d290bbc58dbedf0babeb7bc561aee106c8bbad2da07fd34528467fed17676542`
- agent-workflow run 49: `551e7dd95adc926c5881454f25a9ed69bec60a31250059d5595cd9b942b9d2bf`
- agent-workflow run 50: `a0ee0767935ec4c134a7bf8683efea0797f5f80206c4246c5d964d0890e2b956`
- orders-service run 47: `8438d7858fdfb383071676b7da783c1a9be88a63e0f138af2b20a0dc9e8b2a7c`
- orders-service run 48: `26e1956cbe5bb619b65ea49da5c2b64a132ffc066e247623528f6188015aa369`
- orders-service run 49: `55aceeca5beacb7685bc1ae5c00aa57893bb95ff809747f4d84b930e0f8a50b8`
- orders-service run 50: `056f1b366e7c06b3fd52bf75864638b5c388d9a6ee945e839b0e56a2611f7b15`
- go-ratelimiter run 47: `46a980a3ce123eb951ba23199efe4821f8054b17d4874ab169c5919ec779aba5`
- go-ratelimiter run 48: `120b02dc8e8b570ecb226ae553caf7830231c58decbeaa7e3917d1f8f279f389`
- go-ratelimiter run 49: `d556409cfeee7fa29ab8c0d7576f2a82218fd876aa7c07b2e19af9cd8104d9e4`
- go-ratelimiter run 50: `8d93b2b9515bd5a1eaab4c2a8d963776f61f7c3073076d803e3eccff1bcad2cd`

Mean time and cost reported by the CLI: Opus 2.6 minutes and USD 0.61; Sonnet 1.0 minute and USD
0.21; Haiku 5.5 3.7 minutes and USD 0.04.

Notes:

- Haiku 5.5 found every seeded gap, passed the scorer in four of six reports, copied no secret, and
  cited no line outside a file. Haiku 4.5 had found 72 of 100 and passed once in 12 reports.
- Sonnet still cited lines beyond the end of a file: six citations in three reports, against seven
  in three in runs 41 to 46. Every one came from a single command that numbered several files, such
  as `cat -n README.md go.mod limiter.go` or `cat -n tests/*.py`, whose count continues across the
  files. The rule to take line numbers from output that shows them did not prevent it, because that
  output does show them. Opus and Haiku 5.5 cited no line outside a file.
- Opus noticed the wall-clock test of the reserved go-ratelimiter case but filed it under TEST-02
  and marked TEST-08 not applicable. As before, OPS-02 was not among Opus's first five actions on
  orders-service; Haiku 5.5 also left it out.
- The four false flags are `low` findings on criteria that hold: workflow secrets under CI-03,
  duplicate push and pull request runs under CI-04, ESLint dependencies under TOOL-01, and ignore
  patterns for files that do not exist under REPO-04.
- No report copied a secret, and every prepared repository was unchanged afterwards. Some runs
  read remote state with read-only `gh` commands, which the skill allows; their output masked the
  token. A file `/tmp/t.py` appeared during the round, but no run's stream mentions it.
- A real audit of one of the maintainer's projects ran in the same round; its results are recorded
  after the maintainer reviews them.
- The reserved go-ratelimiter case is recorded like the others; by its definition, these results
  do not change the skill.

## 2026-10-17 — Real audit of a private project

- Skill `8b2a2c6`, Opus 5.5 (`claude-opus-5-5`), Claude Code 2.1.299, headless with the agent and
  prompt of runs 47 to 50, in the same round. The audited repository is one of the maintainer's
  private projects, an application developed with coding agents (about 1,800 tracked files and 700
  commits), cloned at a pinned commit without a remote. The report and the project stay private;
  only the counts below are recorded.
- The audit read the documentation, manifests, and CI in full, sampled about 10% of the maintained
  files with two read-only helpers whose key evidence it re-read, and read hosting state through
  read-only `gh` commands. It reported 32 findings: 2 high, 11 medium, and 19 low. The CLI reported
  5.5 minutes and USD 6.81. The clone was unchanged afterwards.
- Review: an agent proposed a label with evidence for each high and medium finding against the
  audited commit, and the maintainer confirmed them. The low findings were not reviewed.

| Label | High and medium findings |
| --- | --- |
| Correct | 4 |
| Correct, already recorded as known debt or a decision | 3 |
| Real, but rated too high (low was due) | 3 |
| Partly correct | 2 |
| Wrong | 1 |

Notes:

- Ten of 13 high and medium findings describe a real problem, two are partly right, and one is
  wrong. Every priority error was too high: three medium findings deserved low, and one high
  finding deserved medium.
- Most errors share one cause. The audit judged CI, branch protection, and agent review without
  reading the project's documented integration path: a local gate whose passing receipt for the
  exact head the merge tool requires. Without it, a CI outage read as "nothing was validated", the
  documented administrator merge read as a bypass, and one agent-review finding was wrong.
- The audit classified an internal, unsigned pre-release used by its maintainer as a distributed
  product, security level 2, which made distribution criteria such as a software bill of materials
  and a public reporting channel apply.
- One citation did not support its claim: the audit inferred that a tool was missing from one line
  while the next lines ran it. One count, repeated in three findings, was a fifth of the real one.
- The reviewer added one gap the audit missed: the gate's receipts are local and unsigned, so the
  only evidence of each merge comes from the author's machine.

## 2026-10-17 — Runs 51 to 58 (integration path, distribution, absence, and counts)

- Runs 51 to 54 audit the cases with skill `4230dfe`, which adds the rules of the real audit: check
  the integration path before reporting CI or review gaps, count a product as distributed only when
  people outside its team receive it, ground absence claims in a search, and name the command of
  each count. It also carries `5d2a25f`, which numbers each cited file on its own.
- Runs 55 to 58 compare the skill without and with those rules on a large private case, prepared
  with `tools.evals` from a pinned commit of one of the maintainer's projects with five seeded
  defects: runs 55 and 56 use `85094a0` (the skill of `5d2a25f`), runs 57 and 58 use `4230dfe`.
  Its expected findings are five seeds and five gaps the maintainer confirmed in the real audit;
  four criteria must not be flagged, and the seeded token must not appear.
- Agent: Claude Code 2.1.299 through `tools/claude_rounds.py` (`85094a0`), full model IDs, user
  settings only, hooks off, effort high. Every stream names the requested model. The cost limits of
  `533db9b` were approved before these runs.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 51 | Opus 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 52 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 53 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 54 | Haiku 5.5 | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 51 | Opus 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 52 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 53 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 54 | Haiku 5.5 | 13 of 13 | no | 3 of 3 | uncovered 1 |
| well-maintained | 51 | Opus 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 52 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 53 | Sonnet 5.5 | 2 of 2 | no | 2 of 2 | false flag ARCH-05, CI-04, REPO-01, TEST-05 |
| well-maintained | 54 | Haiku 5.5 | 2 of 2 | no | 2 of 2 | false flag QUAL-01, REPO-04 |
| agent-workflow | 51 | Opus 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 52 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 53 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 54 | Haiku 5.5 | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 51 | Opus 5.5 | 9 of 9 | no | 2 of 3 | uncovered 1 |
| orders-service | 52 | Sonnet 5.5 | 9 of 9 | no | 2 of 3 | uncovered 1 |
| orders-service | 53 | Sonnet 5.5 | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 54 | Haiku 5.5 | 9 of 9 | yes | 2 of 3 | — |
| go-ratelimiter | 51 | Opus 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 52 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 53 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 54 | Haiku 5.5 | 4 of 4 | yes | — | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 | 50 of 50 | 5 of 6 | 13 of 14 | 0 | 0 | 17 | 3.2 | 0.81 | 11 | 393,555 | 20,894 |
| Sonnet 5.5 | 100 of 100 | 10 of 12 | 27 of 28 | 0 | 0 | 30 | 2.1 | 0.33 | 10 | 316,519 | 15,424 |
| Haiku 5.5 | 50 of 50 | 4 of 6 | 13 of 14 | 0 | 1 | 19 | 5.6 | 0.12 | 16 | 605,075 | 81,578 |

The same columns for runs 47 to 50, computed from their streams: Opus 2.6 minutes, USD 0.61, 9
tool calls, 260,126 input and 14,872 output tokens; Sonnet 1.0, USD 0.21, 7, 184,782, and 8,498;
Haiku 5.5 3.7, USD 0.04, 12, 437,960, and 49,308.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| large-private | 55 | Opus 5.5 | 9 of 10 (missed SEC-10) | no | 1 of 1 | — |
| large-private | 56 | Opus 5.5 | 3 of 10 (missed ARCH-05, REPO-06, SEC-02, SEC-05, SEC-10, SEC-11, TEST-08) | no | 1 of 1 | bad citations 1 |
| large-private | 57 | Opus 5.5 | 9 of 10 (missed SEC-10) | no | 1 of 1 | false flag AGENT-03 |
| large-private | 58 | Opus 5.5 | 9 of 10 (missed SEC-10) | no | 1 of 1 | false flag AGENT-03 |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 | 12 of 20 | 0 of 2 | 2 of 2 | 1 | 0 | 3 | 7.0 | 9.24 | 252 | 18,887,904 | 112,930 |
| Opus 5.5 | 18 of 20 | 0 of 2 | 2 of 2 | 0 | 1 | 4 | 11.9 | 10.34 | 291 | 21,210,890 | 125,736 |

The first total row is runs 55 and 56; the second is runs 57 and 58.

Report SHA-256 hashes, as printed by the summary:

- python-service run 51: `88245d0b8ee058c3ec04b8dc036c7b98cf5be4b985193cdc341c70e5c4a8e62b`
- python-service run 52: `b11feb2c7dbbaac3780b50741c205c5b2364d021e1ca525a74c8336d013ca0dc`
- python-service run 53: `e7c302c41eef0ef448ce9cb14265203142520f4162f6ee9e5e2ecef9a1a00194`
- python-service run 54: `f1f272c393897cdb9cec7468797be9999c47fb7c0c5e0be2c791dd978df1b01b`
- typescript-cli run 51: `68f7eece7aa30be1af2dd8880e4d605464459fd782736d0f2681a3ce4d5fe02b`
- typescript-cli run 52: `91d1104ec3a952b9b7f32632bf477ba544e91a12a4411a1483c3397742bc7908`
- typescript-cli run 53: `554cfd90f918f5ede6b5d87b985a8939695ca83182429e2c6f177287474afca7`
- typescript-cli run 54: `edfbf840ea664fa33850eb33bd09f2dc961ccfb6939c11d146d33f4acce0cba7`
- well-maintained run 51: `e46da971500a45b411312ab09d9b2f89ea86be646afb9479d1f277fbf963126c`
- well-maintained run 52: `eaffb0adaac4c2e974bc8db05cdfbdada5645800e7c3b581b27d0faad0422e9d`
- well-maintained run 53: `dd18dafbbe815a9ab5334f6f0b9efb96648e3f50e310c819d59ab8c6d627d47a`
- well-maintained run 54: `98cf610046b9525aecbf92dcfa15364c18744444905a5ea2c6d990185a07c559`
- agent-workflow run 51: `2772a75a962bc44895f4ccb0767bee7bfb4e6946a6e4b71fd85cc488a5de1973`
- agent-workflow run 52: `1e50a7db0d4f88ba3ae40c6fc7bc59c47c8992ee04460f493c8c61093f892850`
- agent-workflow run 53: `04892fc1cc8fdd85c9aee303ecd83b07cae3e7080bb501e06d6339365b7a4883`
- agent-workflow run 54: `66e08b89b457c75ec566351c689f875e61ee12683896e311ee6e04ecc399d8fd`
- orders-service run 51: `60132437a4c81117d3bd1815fd87d678456519fe6a9c275d5bb17597e9be7ceb`
- orders-service run 52: `34e321050092b0be1ab75220eea9dde7d0963135ea67620615b74097cf0e0e5d`
- orders-service run 53: `acd5cc1b2a9ecd6e591f557d99a8262f0fab6ddc65faee92b00fb185aa0b1182`
- orders-service run 54: `e0b2995456361d4614a4e7776306316879afb0770b3680eb3e10b5cff7597270`
- go-ratelimiter run 51: `662083676acf8702985ea80bde1014a4fa01da2c327d5ff6ccf526ac12057d39`
- go-ratelimiter run 52: `864fcdce7e8859d48f30554807d43833c0eba958465c50d742a9909036ff0fd6`
- go-ratelimiter run 53: `3bd6da004161375e495cb2b7cb64c502c862a7430277eac6356e909bd5e3fced`
- go-ratelimiter run 54: `d0ae4887736caca3b8e1699d1ed9a3384f1bb261f61c9262d2d53a384e12b19f`
- large-private run 55: `8cdfe8044242847fc3ff2ca7d930ef2b295ffc00950feb9dcf5bc8946c711d0e`
- large-private run 56: `d348147090a21e3b79c456222245976480b9a2aaabeff7067a194911fe5ef56f`
- large-private run 57: `cfce54a44dd6f040412be6475cccdf39f92a01477a7f702b3d06c67f0f94257b`
- large-private run 58: `8f17a07dec9e6e4f99ed54dfaa8dfa1f5b41e04f2af849212381f5ae2356fb2e`

Notes:

- On the cases, every model found every seeded gap, Sonnet passed the scorer in 10 of 12 reports
  against 7 of 12, and no report cited a line outside a file, against six in runs 47 to 50. Mean cost
  rose by 33% for Opus, 57% for Sonnet, and 200% for Haiku 5.5, and time by 23%, 110%, and 51%, with
  more tool calls and 40% to 80% more output tokens. By the approved limits this is a regression.
  The rounds cannot tell how much comes from numbering each file on its own and how much from the
  new rules, and one run per case and model does not measure run-to-run variation.
- On the large case, the new rules raised mean cost by 12% and time by 70%. Runs 55 and 56 used
  background helpers and runs 57 and 58 did not, which accounts for most of the time; tool calls
  rose by 15%. By the approved limits this is a regression on time.
- The distribution rule worked: runs 57 and 58 rated the project level 1 and closed three
  distribution criteria that runs 55 and 56 had flagged, one with a search for mutation tools.
- With the integration-path rule, both runs read the merge gate. Run 58 found the gap the reviewer
  had added, that the gate's receipts are unsigned local files, and filed it under AGENT-03, which
  the case expects unflagged because the real audit's AGENT-03 claim was wrong; the scorer counts
  the criterion, not the claim. Run 57 flagged AGENT-03 because a seeded token landed in a commit
  whose message describes a byte-for-byte move.
- The case itself had three faults. Its rewritten commits do not exist on the hosting service that
  the project's documentation names, and the audits queried that service, so run 56 concluded that
  the remote did not belong to the history and found three of ten gaps. Folding a seed into a
  commit whose message does not cover it is visible to an audit that compares messages with diffs.
  All four runs read the seeded log line of SEC-10 and did not report it; at level 1, with local
  logs of the user's own data, that is a defensible reading, so the seed does not test SEC-10.
- No report copied the seeded token, and every prepared repository was unchanged afterwards. One
  Haiku run listed the global Node modules directory outside its repository.

## 2026-10-17 — Runs 59 to 62 (which change raised the cost)

- Two rounds with Sonnet only, twice per case, to attribute the cost rise of runs 51 to 54: runs 59
  and 60 use `5d2a25f`, which only adds numbering each cited file on its own to the skill of runs 47
  to 50; runs 61 and 62 use `c89e1aa`, which adds the distribution, absence, and count rules and
  replaces the integration-path exploration with a Deeper checks section. Opus, Haiku, and the large
  case wait for a stable candidate, as the maintainer decided.
- Agent as in runs 51 to 58: Claude Code 2.1.299, `tools/claude_rounds.py`, user settings only,
  hooks off, effort high. Every stream names `claude-sonnet-5-5`.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 59 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 60 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 61 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 62 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 59 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 60 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 61 | Sonnet 5.5 | 13 of 13 | no | 3 of 3 | uncovered 1 |
| typescript-cli | 62 | Sonnet 5.5 | 13 of 13 | no | 3 of 3 | duplicated 1 |
| well-maintained | 59 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 60 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 61 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 62 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| agent-workflow | 59 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 60 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 61 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 62 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 59 | Sonnet 5.5 | 9 of 9 | no | 3 of 3 | duplicated 2 |
| orders-service | 60 | Sonnet 5.5 | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 61 | Sonnet 5.5 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 62 | Sonnet 5.5 | 9 of 9 | no | 3 of 3 | duplicated 1 |
| go-ratelimiter | 59 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 60 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 61 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 62 | Sonnet 5.5 | 4 of 4 | yes | — | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5.5, runs 59 and 60 | 100 of 100 | 11 of 12 | 28 of 28 | 0 | 2 | 33 | 1.8 | 0.30 | 9 | 276,345 | 14,242 |
| Sonnet 5.5, runs 61 and 62 | 100 of 100 | 9 of 12 | 27 of 28 | 0 | 0 | 30 | 1.9 | 0.33 | 10 | 280,824 | 15,330 |

Report SHA-256 hashes, as printed by the summary:

- python-service run 59: `793b323bbff52a459cb8b038ec9fb0d33a4dd2dce962f25b5ebb79c319b4ba48`
- python-service run 60: `2421d40a8153fdd31a460586f67ac551f33f7dd8d05d59196d9f883f2c6d1a19`
- python-service run 61: `00556720ccbb72c2a3640d5e894319ee3d71565b72cd6092d217065d42ac4b73`
- python-service run 62: `c014bd115a970f28fbbd4485c0bf12012e61dcf0e27f0dfac4332ab5d0603161`
- typescript-cli run 59: `8dbdeae8b737a5da45b9a4a600e843b7f66b60d714ebce30b77caf72900e04d1`
- typescript-cli run 60: `cca2ab054360af3812acd8a292909405597af4914b7a44bf1d16cf879d41c1a5`
- typescript-cli run 61: `c22b31d98e1428e87c0210bb2a308c9c32db195fc02b53fa5ee4833261587a7d`
- typescript-cli run 62: `7816e6bbe5355ef22eeea902de031142246fca1e9ae484b4f946b787387049a4`
- well-maintained run 59: `89cd7609c48c31dce82d37b74fb588ce64ccc6aece90509bd14393e01f3de72d`
- well-maintained run 60: `687537e658c8e8ec4f762fd324c94ae6f09e526c84d9febe35cffa2591934212`
- well-maintained run 61: `0feec82f476960c2fd0af93c5b84cb7ad5e952e755b02097d44e4e7c0500a2c2`
- well-maintained run 62: `70394d11cc5b6481703998a13ab0857a7cb79b0ba29dc2259cc026d316d686a0`
- agent-workflow run 59: `df6e23c430f98f78186fffa973daed7b160a6df19debec752d957cfb4fcc7d29`
- agent-workflow run 60: `c7f43619e7f337b9a6eca37e3f69b0a4c0e666083b973eb3d0da9333aedaeac7`
- agent-workflow run 61: `7e13cf961942b5ccadef12c668b39ae5e5ad098f81e272edf3eaf6acd48127df`
- agent-workflow run 62: `e48e097ed2f63b22a17afaa092f37baf2c387f8a6c7c7f471ac227be7311791a`
- orders-service run 59: `7df12aa1a4c6e8fa236365a2b248465f1836d15d968bbb877300169ebf346c38`
- orders-service run 60: `df6d91274245450d776d04eef1d2505b91c4d0c2fd5a69d524262add0fb4f330`
- orders-service run 61: `dbf322c9d9cae508470b69c5225637ec269a0622dd6a1d71e3dae83f291bd05f`
- orders-service run 62: `cdd67249d60d489d1362f4642feb71425a3381d7dd0faa8b31700c68a7994bed`
- go-ratelimiter run 59: `cc7cfae7c5f31b8791026ba15773fafabdc9bae00fc71cb31c55252d244db30f`
- go-ratelimiter run 60: `4ebfb4fcabfd5d81274262704c87084694ee7fa75f4509c00bcad8202bc61fcb`
- go-ratelimiter run 61: `43db0d97e92b13d70f12e4e1189b2b3b72e1c83ed78ab7808ee14f8b89ab9c25`
- go-ratelimiter run 62: `accabe4ad6b750a39384fbff749597afa2e2e5d02ea43311c5c7e2c11ea60a96`

Notes:

- Against runs 48 and 49, the same model with `8b2a2c6`: mean cost USD 0.21, 0.30, and 0.33; tool
  calls 7, 9, and 10; output tokens 8,498, 14,242, and 15,330; minutes 1.0, 1.8, and 1.9. Between the
  two runs of one case, cost differs by 7% to 10% on average.
- Numbering each file on its own accounts for most of the rise: 43% more cost, with 42% more shell
  calls as files are read one at a time. It also removed every citation outside a file: none in 24
  reports, against six in 12 for runs 48 and 49. The other rules add 10% more, about the
  run-to-run difference, at the approved limit for the cases.
- These rounds did not repeat `8b2a2c6`, so a change in the service between runs 48 and 59 would
  look like a cost of the skill.
- Every report listed one to five Deeper checks, 3.3 on average. Those read name a concrete premise,
  its effect, and a check, such as asking the owner whether a password is a placeholder or reading
  branch protection once a remote exists.

## 2026-10-17 — Runs 63 to 65 (a baseline measured again)

- Run 63 repeats `8b2a2c6`, the skill of runs 47 to 50, once per case; runs 64 and 65 test the
  candidate `63b733b`, which reads several files at once with per-file line numbers and keeps the
  rules and Deeper checks of `c89e1aa`. Sonnet only, from 16:20 to 16:28 UTC; runs 48 and 49 ran
  from 12:07. The agent is as in runs 59 to 62. A second repetition of `8b2a2c6` was planned but
  not run.
- Decision rule, fixed before the runs: no cited line outside a file, and mean cost at most 10% above
  run 63.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 63 | Sonnet 5.5 | 16 of 16 | no | 3 of 3 | unmarked high 1 |
| python-service | 64 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 65 | Sonnet 5.5 | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 63 | Sonnet 5.5 | 13 of 13 | no | 3 of 3 | duplicated 9 |
| typescript-cli | 64 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 65 | Sonnet 5.5 | 13 of 13 | yes | 3 of 3 | — |
| well-maintained | 63 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 64 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 65 | Sonnet 5.5 | 2 of 2 | yes | 2 of 2 | — |
| agent-workflow | 63 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 64 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 65 | Sonnet 5.5 | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 63 | Sonnet 5.5 | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 64 | Sonnet 5.5 | 9 of 9 | no | 2 of 3 | uncovered 6 |
| orders-service | 65 | Sonnet 5.5 | 9 of 9 | yes | 2 of 3 | — |
| go-ratelimiter | 63 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 64 | Sonnet 5.5 | 4 of 4 | yes | — | — |
| go-ratelimiter | 65 | Sonnet 5.5 | 4 of 4 | no | — | uncovered 1 |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5.5, run 63 | 50 of 50 | 4 of 6 | 14 of 14 | 0 | 1 | 16 | 1.7 | 0.30 | 10 | 280,367 | 14,103 |
| Sonnet 5.5, runs 64 and 65 | 100 of 100 | 10 of 12 | 26 of 28 | 0 | 0 | 28 | 1.9 | 0.34 | 9 | 285,442 | 16,323 |

Report SHA-256 hashes, as printed by the summary:

- python-service run 63: `fe96f0d2c43f58ed8d5c1922f57aee8b27c338f895fdc591ade0b680e424dffd`
- python-service run 64: `615f0734a956197ca692a30e17ff69088d3236a40bbb60a20d50562625bc60d7`
- python-service run 65: `448f3667fba85a97babbbbcaf05b99c2f77456a14cbf0966b19edb7836be8092`
- typescript-cli run 63: `50b24d814742d42763f1e0cb70cc2d591a792a612ff3414bd418be333bbaf821`
- typescript-cli run 64: `32c6569c863a903687d2b96e97504b6739e1850486d0af2222beb51b735a011e`
- typescript-cli run 65: `af664e44655076546125e43786592b6de0bd39cfaadfe961dfe65b158b95d74d`
- well-maintained run 63: `f5e31636be2d09f5e1dfc82747a7abde7a5e5387a4870ef7ee24dd04783a1634`
- well-maintained run 64: `37725a000622e657198bbe64394ab62429e653a65ab886900da7b5ef3dce6e33`
- well-maintained run 65: `35cb2e7baf234de5bc3953aa73b42b29301741142ddd31c89312ff2e9a6be4c7`
- agent-workflow run 63: `69474cf1ac0ad8d5140427fab79c04157646e1afc7570177f7920b8906b326d7`
- agent-workflow run 64: `060ded6a313d38a15dda85522c5fe6a4bdd825b0171f9681a0eb9046ae0b4b33`
- agent-workflow run 65: `d47e64eabdbe3412f555700e0215450408f32af1cb33d8886e47f0333e62d4eb`
- orders-service run 63: `fe9e1749ae3997a81f46fab08d9c7ba494b594eb1a57c16ce00508119ad4b124`
- orders-service run 64: `4c8cfef5f5f55381c111953f7c8e616d068e930a6dca190598896311f1c40b2d`
- orders-service run 65: `0538647fc6bc4ec345ca6c19bf06edcc38bd6fa61842b6927f6ab70ecada9f38`
- go-ratelimiter run 63: `508ed19c7fdb13ec20c0825818feca65390463ca3f3b08d8a29159207943f203`
- go-ratelimiter run 64: `09622064d5565d9c356bfb36ec54a5fea0996294af732aef1ce49f59e882dbce`
- go-ratelimiter run 65: `31ee8ad708a124374e0d30045b51b89e0dec594550c680b5ee13c84ccb9aa492`

Notes:

- The same skill cost USD 0.30 in run 63 and USD 0.21 in runs 48 and 49, with 14,103 output tokens
  against 8,498 and no cited line outside a file against six. The service changed between the
  morning and the afternoon. The 43% rise that runs 59 to 62 attributed to numbering each file is
  that change: `5d2a25f` cost USD 0.30 at 15:22, as `8b2a2c6` did at 16:20.
- The candidate cited no line outside a file or on a wrong line, and cost 13% more than run 63, with
  16% more output tokens and one tool call fewer. Against one repetition of the baseline, whose
  runs differ by about 10%, that is at the limit rather than clearly over it.
- Comparisons with rounds run hours apart are not reliable. A round that tests a change needs a
  control arm run alongside it.

## 2026-10-17 — Runs 66 to 73 (control and candidate side by side)

- The first round with a control arm: `8b2a2c6`, the skill of runs 47 to 50, against the candidate
  `63b733b`, with Sonnet and Haiku 5.5 twice per arm and case, interleaved case by case from 18:00
  to 18:22 UTC with `e5d5936`. Agent otherwise as in runs 59 to 65.
- Decision rule, fixed before the runs, for each model: the candidate cites no line outside a file,
  loses no seeded gap, adds no false flag that the control lacks, and costs at most 10% more than
  the control.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 66 | Sonnet 5.5 @ 8b2a2c6 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 67 | Sonnet 5.5 @ 63b733b | 16 of 16 | yes | 3 of 3 | — |
| python-service | 68 | Sonnet 5.5 @ 8b2a2c6 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 69 | Sonnet 5.5 @ 63b733b | 16 of 16 | yes | 3 of 3 | — |
| python-service | 70 | Haiku 5.5 @ 8b2a2c6 | 16 of 16 | no | 3 of 3 | secret copied |
| python-service | 71 | Haiku 5.5 @ 63b733b | 16 of 16 | no | 3 of 3 | secret copied |
| python-service | 72 | Haiku 5.5 @ 8b2a2c6 | 16 of 16 | no | 3 of 3 | unmarked high 1 |
| python-service | 73 | Haiku 5.5 @ 63b733b | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 66 | Sonnet 5.5 @ 8b2a2c6 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 67 | Sonnet 5.5 @ 63b733b | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 68 | Sonnet 5.5 @ 8b2a2c6 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 69 | Sonnet 5.5 @ 63b733b | 13 of 13 | no | 3 of 3 | uncovered 1, duplicated 3 |
| typescript-cli | 70 | Haiku 5.5 @ 8b2a2c6 | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 71 | Haiku 5.5 @ 63b733b | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 72 | Haiku 5.5 @ 8b2a2c6 | 13 of 13 | no | 3 of 3 | uncovered 13, false flag TOOL-01 |
| typescript-cli | 73 | Haiku 5.5 @ 63b733b | 13 of 13 | yes | 3 of 3 | — |
| well-maintained | 66 | Sonnet 5.5 @ 8b2a2c6 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 67 | Sonnet 5.5 @ 63b733b | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 68 | Sonnet 5.5 @ 8b2a2c6 | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| well-maintained | 69 | Sonnet 5.5 @ 63b733b | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| well-maintained | 70 | Haiku 5.5 @ 8b2a2c6 | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| well-maintained | 71 | Haiku 5.5 @ 63b733b | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| well-maintained | 72 | Haiku 5.5 @ 8b2a2c6 | 2 of 2 | no | 2 of 2 | false flag QUAL-01 |
| well-maintained | 73 | Haiku 5.5 @ 63b733b | 2 of 2 | no | 2 of 2 | false flag REPO-04 |
| agent-workflow | 66 | Sonnet 5.5 @ 8b2a2c6 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 67 | Sonnet 5.5 @ 63b733b | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 68 | Sonnet 5.5 @ 8b2a2c6 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 69 | Sonnet 5.5 @ 63b733b | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 70 | Haiku 5.5 @ 8b2a2c6 | 6 of 6 | no | 3 of 3 | uncovered 3 |
| agent-workflow | 71 | Haiku 5.5 @ 63b733b | 6 of 6 | no | 2 of 3 | uncovered 4 |
| agent-workflow | 72 | Haiku 5.5 @ 8b2a2c6 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 73 | Haiku 5.5 @ 63b733b | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 66 | Sonnet 5.5 @ 8b2a2c6 | 9 of 9 | no | 3 of 3 | duplicated 1 |
| orders-service | 67 | Sonnet 5.5 @ 63b733b | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 68 | Sonnet 5.5 @ 8b2a2c6 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 69 | Sonnet 5.5 @ 63b733b | 9 of 9 | yes | 3 of 3 | — |
| orders-service | 70 | Haiku 5.5 @ 8b2a2c6 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 71 | Haiku 5.5 @ 63b733b | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 72 | Haiku 5.5 @ 8b2a2c6 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 73 | Haiku 5.5 @ 63b733b | 9 of 9 | yes | 2 of 3 | — |
| go-ratelimiter | 66 | Sonnet 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 67 | Sonnet 5.5 @ 63b733b | 4 of 4 | yes | — | — |
| go-ratelimiter | 68 | Sonnet 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 69 | Sonnet 5.5 @ 63b733b | 4 of 4 | yes | — | — |
| go-ratelimiter | 70 | Haiku 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 71 | Haiku 5.5 @ 63b733b | 4 of 4 | yes | — | — |
| go-ratelimiter | 72 | Haiku 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 73 | Haiku 5.5 @ 63b733b | 4 of 4 | yes | — | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5.5 @ 8b2a2c6 | 100 of 100 | 10 of 12 | 27 of 28 | 0 | 1 | 29 | 1.7 | 0.31 | 9 | 265,203 | 14,971 |
| Sonnet 5.5 @ 63b733b | 100 of 100 | 10 of 12 | 27 of 28 | 0 | 3 | 28 | 1.9 | 0.34 | 10 | 308,161 | 16,118 |
| Haiku 5.5 @ 8b2a2c6 | 100 of 100 | 6 of 12 | 26 of 28 | 0 | 0 | 37 | 5.3 | 0.12 | 17 | 640,845 | 73,573 |
| Haiku 5.5 @ 63b733b | 100 of 100 | 8 of 12 | 25 of 28 | 0 | 0 | 30 | 5.5 | 0.12 | 14 | 611,288 | 77,255 |

Report SHA-256 hashes, as printed by the summary:

- python-service run 66: `148ce7eb30db941d5da8c7b7d1d7930b4b475e06d28ecd4005569bcb8ad90778`
- python-service run 67: `9478c05a94971f766118b1920979ddf735af2095a22090dde3c8c879e9bfd0bf`
- python-service run 68: `ebea128df6df4bc0677dbb6bcd9fbc16beea810c1c0076389e0c6fd9893314d2`
- python-service run 69: `f7115f80c5b5bee8fe8ee4a12c078dd5ba0f557cc2915eb04354a0a8f8204065`
- python-service run 70: `3cf4748c3ccd3cace10e82d9f1e07bac038b72181d1cf4ff5c435feb2e27fd2a`
- python-service run 71: `560bbdeccb9235e29d95b344a3a415483045a9639bbfaa0850982e6a2756d758`
- python-service run 72: `5ca8685a4e967efbb9621c097531e2c56ed57b22908bb3eeaec2c93e40935c4e`
- python-service run 73: `956a7630c4b4cf9edb9e2f337c3a3f014b60c91f6ca7c7f29cc3bfdb5fdf9139`
- typescript-cli run 66: `ab947add868feb912d8fa746904d208e1e3173ccaa08e517987bcd65be805624`
- typescript-cli run 67: `19ede85e2c221cdff7801f874550ec41ea1eaad0e4b4af1e713dbb284522b814`
- typescript-cli run 68: `eb5cb84d44c3b00bd6783d80875a38957d25a86c3899d1d402c6382da83713cf`
- typescript-cli run 69: `0f0a9ee055215e58b12187552106adeea2ff3e5b73adb59a1b14454ab4d6a26d`
- typescript-cli run 70: `6bc36f7d151481adf3af8b91d8ee2449b3238e4c4d37e34e15d2e0ac28334d41`
- typescript-cli run 71: `1702f44853410c14c212a8381b3d0d800c6a7956e07450b01ff684a62a94e0f7`
- typescript-cli run 72: `606bdf59f3b067b27293d701835b7cc1b007a07f02d97d113fb1c9f21af399d1`
- typescript-cli run 73: `77fb92a9396a4dc3de749daf488ad7b52ec3f09c88bec12462da76b5c8f8164d`
- well-maintained run 66: `2669825e2e05e3f827dcd8d7e0393a4ecc2cfed739c75cd438d010a8a187f4fe`
- well-maintained run 67: `824b3ec75a0ebb2d405afdfa102b4ee79dcd4c233db1c99f0fa46928908ee192`
- well-maintained run 68: `4a41547bae43516d4d7deeac0745ffbae2a7e2b2103c537b75163bfe1772c664`
- well-maintained run 69: `50526b073be4334dd673d41d61de7625416b7fd96bb5d0bf490717bdc964ba34`
- well-maintained run 70: `9d36f7e9c9d2d4abc0ad89d47f998846742ed82ba2f0c2b5003bdd7161a5abbf`
- well-maintained run 71: `2ec5a59bd868ce10c70ddc25ebb22cbc7ae81f5d20b71af636592ac86a0da2ec`
- well-maintained run 72: `df24324ec3e31547d1aea123df6c5647c65861bced0129884e564d1d2cedb4e6`
- well-maintained run 73: `1b249e08cbe3092f43863cfb5d7cf1f22b5345a74647be7cb2a05a4aa68d7bba`
- agent-workflow run 66: `6a6fc6ee4c63592092652646134b2b14c51f9588b33e78040c3d5120bdd3d99c`
- agent-workflow run 67: `4c54c0191b57db7fd2f01fc130c846b472a0460309a363758f40314c67d68318`
- agent-workflow run 68: `f9a6b1fdaeb0cc73c9863927a216f10c8770f3d42ad4fbb839f5e044c07ecf30`
- agent-workflow run 69: `8e2c40bfe2cc8d504ba02fc42796be44a61cc88ecacdcb17b8576283cdb236dd`
- agent-workflow run 70: `fb10dca848c9b768f24c07e99133183fd0b66789e7abc2781a42257fef84aa90`
- agent-workflow run 71: `b3fea1926a5895987472ebd2c988759551976bfc2a90dd5101860e576346bae8`
- agent-workflow run 72: `cd8c2f1b5d22b51e77135080a8e417d02110edc95028e5c78d64b1db78128192`
- agent-workflow run 73: `6ed19c7ff69513fc2117d32c04eae3368f81829e3d31a06836d1930e94bd5915`
- orders-service run 66: `3927fa7cc7a7f042dea2512386a2e1691d719deab50b2e85b5ff51062c14f0cd`
- orders-service run 67: `dc5e0d9e77cae73479c89f19b25cec4ec7673f9653a7344313384d63bdc3eae8`
- orders-service run 68: `45fe1ea954fce918994ca6f1a32ec68f8acc9f012664d016230aa16ce0ff7319`
- orders-service run 69: `492e30694230c387e4e7bcf3f55ffa21a9a87751185a1bc323591f091e84031b`
- orders-service run 70: `7d725ce8320ddbf66b26fd8179ff5bd1115a280c2ebe6b24cd9996db7b937699`
- orders-service run 71: `4f90947e78a18d460fe1ab11964efb87015d02f9b2ccc47764430977369213b0`
- orders-service run 72: `eb75f709164efd1893b2462c13b2df89cdcad6c40e08630d76d60e2b9345427f`
- orders-service run 73: `8c95535ac36e2b1235cad5c123db9dd3aecf21bc7c1cdd436f6cdaa954e37478`
- go-ratelimiter run 66: `d08ed8977c9a0a85bd777e1690a159a39b4d7a12acbfd170ef6d0bf5af288bae`
- go-ratelimiter run 67: `1e5f49b06c4e00b97ee4a7f13fb13301e6410c3244421f42e7325e3fda46e401`
- go-ratelimiter run 68: `5bc55778aa43453db2c9ad5a9ca641bd86e723c512ee13b46b5e7cdcaa886aa0`
- go-ratelimiter run 69: `afa2a04c9d903f71023a119f9d11d42634fa847fbfd781fb913f8ff8c2df7f07`
- go-ratelimiter run 70: `41971f80faf808204afd4ecd185e5a3ff4e57477884449256cb8c12232d05caa`
- go-ratelimiter run 71: `b6f83bb11fd11abbbfaae35f9475428820ae2c4b770ee420f0683933685ad89f`
- go-ratelimiter run 72: `2eabc52c9862ce626ed7167cd57410b1bdab02fafaed4db38417dc3fc0281211`
- go-ratelimiter run 73: `41199f60e5244f0a75435aed0566048d3aa46f72f4483963a64745b5d68f33ac`

Notes:

- The candidate meets the rule for both models. Neither arm cited a line outside a file, both found
  every seeded gap, and the candidate's false flags (REPO-04 for each model) also appear in the
  control. Mean cost rose 9.7% for Sonnet and not at all for Haiku 5.5; per case, the candidate cost
  7% more for Sonnet and 9% more for Haiku 5.5 on average, with Sonnet higher in five of six cases.
- Haiku 5.5 passed the scorer in 8 of 12 candidate reports against 6 of 12 control reports, and
  marked fewer high findings, 30 against 37.
- Haiku 5.5 copied the python-service seeded password in one report per arm. Sonnet had three
  citations of quoted code on another line with the candidate and one with the control; high
  findings now quote their code, which makes such citations checkable.
- The maintainer accepted `63b733b` on 2026-10-17 as the control for later rounds with Sonnet and
  Haiku 5.5; Opus and the large case still have to confirm it. The control is a version, rerun
  beside each candidate, not these numbers.

## 2026-10-17 — Runs 74 to 79 (Opus against the control)

- Opus 5.5 compares the control `8b2a2c6` with the candidate `63b733b`: once per arm on each case
  (runs 74 and 75), and twice per arm on a corrected large private case (runs 76 to 79), from 19:11
  to 19:48 UTC with `377c806`, whose audits have no GitHub CLI login.
- The corrected case keeps the pinned commit and three seeds of runs 55 to 58, moves the realistic
  key to the commit that added that line, replaces the SEC-10 seed with an API key written to a log
  on a failed key check, and no longer expects AGENT-03 unflagged.
- Run 76 used background helpers, and its last result only said that an earlier message held the
  report; the runner saved that sentence. `86ba453` takes the last result with a Findings section,
  and run 76's report was extracted again from its stream. No other saved stream was affected.
- Decision rule, fixed before the runs: on the cases, as for runs 66 to 73, with one run per arm
  only indicative for cost; on the large case, at least the control's gaps, no flag on CI-03,
  CI-10, or DEP-01, no copied key, DEL-04, SEC-07, and TEST-09 below medium, and at most 20% more
  cost and time.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 74 | Opus 5.5 @ 8b2a2c6 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 75 | Opus 5.5 @ 63b733b | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 74 | Opus 5.5 @ 8b2a2c6 | 13 of 13 | no | 3 of 3 | unmarked high 1 |
| typescript-cli | 75 | Opus 5.5 @ 63b733b | 13 of 13 | yes | 3 of 3 | — |
| well-maintained | 74 | Opus 5.5 @ 8b2a2c6 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 75 | Opus 5.5 @ 63b733b | 2 of 2 | yes | 2 of 2 | — |
| agent-workflow | 74 | Opus 5.5 @ 8b2a2c6 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 75 | Opus 5.5 @ 63b733b | 6 of 6 | no | 3 of 3 | uncovered 1 |
| orders-service | 74 | Opus 5.5 @ 8b2a2c6 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 75 | Opus 5.5 @ 63b733b | 9 of 9 | yes | 2 of 3 | — |
| go-ratelimiter | 74 | Opus 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 75 | Opus 5.5 @ 63b733b | 4 of 4 | yes | — | — |
| large-private | 76 | Opus 5.5 @ 8b2a2c6 | 7 of 10 (missed CI-11, SEC-02, SEC-11) | no | 1 of 1 | — |
| large-private | 77 | Opus 5.5 @ 63b733b | 7 of 10 (missed CI-11, REPO-06, SEC-02) | no | 1 of 1 | uncovered 2 |
| large-private | 78 | Opus 5.5 @ 8b2a2c6 | 8 of 10 (missed CI-11, SEC-02) | no | 1 of 1 | — |
| large-private | 79 | Opus 5.5 @ 63b733b | 7 of 10 (missed ARCH-05, CI-11, SEC-02) | no | 1 of 1 | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5, cases, @ 8b2a2c6 | 50 of 50 | 5 of 6 | 13 of 14 | 0 | 0 | 21 | 3.7 | 0.80 | 11 | 410,591 | 20,628 |
| Opus 5.5, cases, @ 63b733b | 50 of 50 | 5 of 6 | 13 of 14 | 0 | 0 | 16 | 4.1 | 0.94 | 12 | 498,918 | 23,856 |
| Opus 5.5, large case, @ 8b2a2c6 | 15 of 20 | 0 of 2 | 2 of 2 | 0 | 1 | 3 | 6.8 | 8.85 | 197 | 17,179,139 | 110,992 |
| Opus 5.5, large case, @ 63b733b | 14 of 20 | 0 of 2 | 2 of 2 | 0 | 0 | 1 | 8.1 | 7.53 | 176 | 14,119,562 | 95,204 |

Report SHA-256 hashes, as printed by the summary:

- python-service run 74: `f1955d1dd1acdf900e9e407acb2bfc33e02afe4b187587e1fa1831e577e1f092`
- python-service run 75: `0670efd820fa750dfb1a94ac38ea6f48ffbe0255290b2d41bf5452afae5ac62a`
- typescript-cli run 74: `4c1f334db0a424d70d08843a7aa4d026e9e4b73c959964b08602af9a9ae84a51`
- typescript-cli run 75: `2a13b2aa215020c718579875527a447875f7a90353f43cd95ad1ccfa07ef70a5`
- well-maintained run 74: `e191b71f046f7209d4ce2cbcc9e7e6abd14af8c037b3e8bf1a9df09c65cdf54a`
- well-maintained run 75: `ec0824bad3db60d05124577d37fd2f099a6feb9571a0bca45f4b4687c01114fd`
- agent-workflow run 74: `09c34bb7d5ac0a3ab42a4956801493fb7254e59ec39bced6242910e2dae7a7fc`
- agent-workflow run 75: `24ba407b0ddaa9b45c6db5b9a4c2fcf9a5c00531038b585c63b49a10a274824a`
- orders-service run 74: `942a62e71fb1b8a8ad7c816fc793c1472c79f903417d68ef0fbced3eeb98372b`
- orders-service run 75: `5681704b572c7804cad7a88d7cabacb47cb3fd5c7c0f9a2219ce50646e55892d`
- go-ratelimiter run 74: `415b71c3bc056df857d58b3090070908cf393238c6b3d449914975ef7f90b28c`
- go-ratelimiter run 75: `af23609b9581034ece3b4b5dd7bc3cafbea04586b79dc3130f87262c3c9f1b21`
- large-private run 76: `471321155f29edf628369e259e5c6eb357c96dc7413c45f40beed7719b791986`
- large-private run 77: `23591e4c49f0a19481fa5c8f6a0384d59d542a695a2981f1e98b819e534d0c4f`
- large-private run 78: `e86a840f63531d4997f5438bab7000fa81144bae575b71f1dcc4a4a7d27bcb0c`
- large-private run 79: `e7d005abce01883fa1226e337f9819f1c7f2f4cb1e30b02ea78b17870028d9be`

Notes:

- On the cases, both arms found every seeded gap and cited no line outside a file. The candidate
  marked fewer high findings, 16 against 21, and cost more in all six cases, 4% to 32% and 17% in
  the mean: above the limit, and consistent across cases rather than noise.
- On the large case, the candidate found 14 of 20 expected gaps against 15, cost 15% less, took 19%
  longer, and used fewer tool calls. Neither arm flagged a criterion expected unflagged or copied the
  key. Both candidate runs rated the project level 1 and left the distribution criteria below
  medium; one control run rated it level 2. The candidate marked one high finding against three.
- Every run missed CI-11 and the SEC-02 seed, so that seed does not separate the versions. The
  candidate missed REPO-06 once and ARCH-05 once, which the control found; the control missed the
  SEC-11 seed once.
- Three runs flagged HIST-03 because the repository's commit-policy check pins exceptions to commit
  SHAs and a tag that the rewritten history no longer has. That is a fault of the case, not of the
  audits.
- The candidate's Deeper checks name concrete premises, such as whether the clone matches the
  hosted history and whether hosted runs passed, each with its check.
- By the rule, the candidate regresses on cost on the cases with Opus and misses one more gap on the
  large case, while costing less on the large case.

## 2026-10-17 — Runs 80 to 82 (the cost of Deeper checks with Opus)

- Opus 5.5 runs the control `8b2a2c6` (run 80) beside two variants of the candidate `63b733b`, once
  per case, interleaved from 20:09 to 20:21 UTC with `86ba453`: `b35f54d` without the Deeper checks
  section (run 81), and `09c8e51` with Deeper checks limited to `high` findings, at most three
  entries of one line each (run 82). Both variants live on evaluation branches.
- Decision rule, fixed before the runs: `09c8e51` becomes the candidate if it meets the rule of runs
  66 to 73 against the control; `b35f54d` only measures what the section costs.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 80 | Opus 5.5 @ 8b2a2c6 | 16 of 16 | yes | 3 of 3 | — |
| python-service | 81 | Opus 5.5 @ b35f54d | 16 of 16 | yes | 3 of 3 | — |
| python-service | 82 | Opus 5.5 @ 09c8e51 | 16 of 16 | yes | 3 of 3 | — |
| typescript-cli | 80 | Opus 5.5 @ 8b2a2c6 | 13 of 13 | no | 3 of 3 | duplicated 1 |
| typescript-cli | 81 | Opus 5.5 @ b35f54d | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 82 | Opus 5.5 @ 09c8e51 | 13 of 13 | yes | 3 of 3 | — |
| well-maintained | 80 | Opus 5.5 @ 8b2a2c6 | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 81 | Opus 5.5 @ b35f54d | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 82 | Opus 5.5 @ 09c8e51 | 2 of 2 | yes | 2 of 2 | — |
| agent-workflow | 80 | Opus 5.5 @ 8b2a2c6 | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 81 | Opus 5.5 @ b35f54d | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 82 | Opus 5.5 @ 09c8e51 | 6 of 6 | yes | 3 of 3 | — |
| orders-service | 80 | Opus 5.5 @ 8b2a2c6 | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 81 | Opus 5.5 @ b35f54d | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 82 | Opus 5.5 @ 09c8e51 | 9 of 9 | no | 2 of 3 | uncovered 1 |
| go-ratelimiter | 80 | Opus 5.5 @ 8b2a2c6 | 4 of 4 | yes | — | — |
| go-ratelimiter | 81 | Opus 5.5 @ b35f54d | 4 of 4 | yes | — | — |
| go-ratelimiter | 82 | Opus 5.5 @ 09c8e51 | 4 of 4 | yes | — | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 @ 8b2a2c6 | 50 of 50 | 5 of 6 | 13 of 14 | 0 | 0 | 17 | 3.2 | 0.77 | 10 | 399,131 | 19,439 |
| Opus 5.5 @ b35f54d | 50 of 50 | 6 of 6 | 13 of 14 | 0 | 0 | 17 | 3.3 | 0.83 | 12 | 457,253 | 20,742 |
| Opus 5.5 @ 09c8e51 | 50 of 50 | 5 of 6 | 13 of 14 | 0 | 0 | 18 | 3.7 | 0.82 | 11 | 399,909 | 21,217 |

Report SHA-256 hashes, as printed by the summary:

- python-service run 80: `4a4d03236b02ca58bd97d5be4299688613603d3a02aca1664e28d0c9a708cc00`
- python-service run 81: `f541dc1f0626348a85289d637dcbb2b7c58ad897c9a469acbd634e87bdacc96b`
- python-service run 82: `d8d7a7f7408374b33c8321305551ed2c2dca5eee8af3857628a908b3eb0574b7`
- typescript-cli run 80: `907453d72618be4fc23976ff803fa2f7764a02892f57cd4b041cbd1b507d2f60`
- typescript-cli run 81: `9f0c28438f52dadc63ca4d4b1874ab6895447bd2c83134b45e6ea9cc193ce7f8`
- typescript-cli run 82: `dd7301bb1993219a51a18364fa0c66a8e3a3ebdc949bf8b4ca8ceb2a6cd0c2a2`
- well-maintained run 80: `7fb3a60954b15734b9a00989dd16ceb0974f24a47f028c8355c4343f448395ae`
- well-maintained run 81: `ea2b00609345e9c84911654c4087ecec1f8bef7b33f9de507059eae8eb23b0ce`
- well-maintained run 82: `a143b9a11bdbd1d0d3fd0ac2bf45f1c6aad2517331507140bedc2198c20d5181`
- agent-workflow run 80: `8d1027c4504fdeabc6300f146af4d57e35c853055173bf9f8f5e63b4fdabb8f9`
- agent-workflow run 81: `8fe987289bf574725940d15efb6c210007d92f64acf5c8244996f751509196a0`
- agent-workflow run 82: `efa337254ba4eda8153350c7111136662a2ca249b978f732417d173edd8248dc`
- orders-service run 80: `73d41991df52c1b31f25b602675b9b4d752b344aed7240e9845254f09ce54664`
- orders-service run 81: `150a1f72aa33116b04fa848dbabbb343dff84982c42d753366a3daeeaa236303`
- orders-service run 82: `46553310b6c8d8757da5912e2a3e9e1c61e197d4923e1e074862542d6c1598b8`
- go-ratelimiter run 80: `977ef7361cdc5d43bd34daf6f7e2c5fbcbfa9dae8b04570857d4abc7ae01b73f`
- go-ratelimiter run 81: `556df9ed0b83d604b0b7f36ee255e2eba6807a893d6913ece84b3fb23f188285`
- go-ratelimiter run 82: `dd21626eb03facea44d0566c45528f7d925d1b81b4578d67912efb82e58bc087`

Notes:

- `09c8e51` meets the rule: every seeded gap, no citation outside a file, no false flag, and mean
  cost 6.5% above the control, 8% in the mean of per-case ratios, higher in five of six cases.
- Without Deeper checks, `b35f54d` cost 8% more than the control, 11% per case, so the section is
  not what raised the candidate's cost; the rest of the change costs Opus about 8% on the cases.
  The candidate's 17% in runs 74 and 75 came from a different hour.
- The limited section listed three entries in four reports and none in two.
- In run 81 a cleanup command passed to `sh -c` with `rm` was refused by Claude Code's safety
  check; no file was left behind.
- The maintainer had decided to freeze the v0.2 skill after this round: the skill of `09c8e51` is
  that version, applied to the main line as `7d06633`.

## 2026-10-17 — Runs 87 to 93 (release level comparison and self-audit)

- The level comparison that conditions v0.2.0: Opus 5.5 runs the frozen skill `7d06633` (runs 87
  and 90), its catalog alone (runs 88 and 91), and no skill (runs 89 and 92) on every case,
  interleaved case by case from 21:19 to 21:38 UTC with `421f553`. The catalog level receives the
  four `criteria*.md` files of `7d06633`, with the prompt of runs 19 to 24 extended to the area
  files and the `not-applicable areas` line; the no-skill prompt is that of runs 19 to 24. The
  no-skill runs show `421f553` as their revision, which gives them no material.
- The criteria of [README.md](README.md#baselines), approved before runs 19 to 24, compare the full
  skill with the catalog over both runs of every case.

| Case | Run | Model | Seeded gaps found | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- |
| python-service | 87 | Opus 5.5 @ 7d06633 full | 16 of 16 | yes | 3 of 3 | — |
| python-service | 88 | Opus 5.5 @ 7d06633 catalog | 16 of 16 | no | 3 of 3 | unmarked high 9, uncovered 1, secret copied |
| python-service | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | secret copied |
| python-service | 90 | Opus 5.5 @ 7d06633 full | 16 of 16 | yes | 3 of 3 | — |
| python-service | 91 | Opus 5.5 @ 7d06633 catalog | 16 of 16 | no | 3 of 3 | unmarked high 13, secret copied |
| python-service | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | secret copied |
| typescript-cli | 87 | Opus 5.5 @ 7d06633 full | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 88 | Opus 5.5 @ 7d06633 catalog | 13 of 13 | no | 3 of 3 | unmarked high 15 |
| typescript-cli | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| typescript-cli | 90 | Opus 5.5 @ 7d06633 full | 13 of 13 | yes | 3 of 3 | — |
| typescript-cli | 91 | Opus 5.5 @ 7d06633 catalog | 13 of 13 | no | 3 of 3 | unmarked high 14, uncovered 1 |
| typescript-cli | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| well-maintained | 87 | Opus 5.5 @ 7d06633 full | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 88 | Opus 5.5 @ 7d06633 catalog | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| well-maintained | 90 | Opus 5.5 @ 7d06633 full | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 91 | Opus 5.5 @ 7d06633 catalog | 2 of 2 | yes | 2 of 2 | — |
| well-maintained | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| agent-workflow | 87 | Opus 5.5 @ 7d06633 full | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 88 | Opus 5.5 @ 7d06633 catalog | 6 of 6 | no | 3 of 3 | unmarked high 9 |
| agent-workflow | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| agent-workflow | 90 | Opus 5.5 @ 7d06633 full | 6 of 6 | yes | 3 of 3 | — |
| agent-workflow | 91 | Opus 5.5 @ 7d06633 catalog | 6 of 6 | no | 3 of 3 | unmarked high 10 |
| agent-workflow | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| orders-service | 87 | Opus 5.5 @ 7d06633 full | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 88 | Opus 5.5 @ 7d06633 catalog | 9 of 9 | no | 3 of 3 | unmarked high 16, secret copied |
| orders-service | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| orders-service | 90 | Opus 5.5 @ 7d06633 full | 9 of 9 | yes | 2 of 3 | — |
| orders-service | 91 | Opus 5.5 @ 7d06633 catalog | 9 of 9 | no | 3 of 3 | unmarked high 15 |
| orders-service | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| go-ratelimiter | 87 | Opus 5.5 @ 7d06633 full | 4 of 4 | yes | — | — |
| go-ratelimiter | 88 | Opus 5.5 @ 7d06633 catalog | 4 of 4 | no | — | unmarked high 7 |
| go-ratelimiter | 89 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |
| go-ratelimiter | 90 | Opus 5.5 @ 7d06633 full | 4 of 4 | yes | — | — |
| go-ratelimiter | 91 | Opus 5.5 @ 7d06633 catalog | 4 of 4 | no | — | unmarked high 6 |
| go-ratelimiter | 92 | Opus 5.5 @ 421f553 none | by hand | by hand | — | — |

| Model | Seeded gaps found | Reports that pass the scorer | Top priorities in first five | Bad citations | Misplaced citations | High findings | Mean minutes | Mean USD | Mean tool calls | Mean input tokens | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Opus 5.5 @ 7d06633 full | 100 of 100 | 12 of 12 | 26 of 28 | 0 | 0 | 37 | 3.6 | 0.96 | 11 | 556,432 | 22,348 |
| Opus 5.5 @ 7d06633 catalog | 100 of 100 | 2 of 12 | 28 of 28 | 0 | 0 | 114 | 2.9 | 0.68 | 5 | 222,655 | 18,504 |
| Opus 5.5 @ 421f553 none | 0 of 0 | 0 of 12 | 0 of 0 | 0 | 0 | 0 | 1.1 | 0.32 | 4 | 178,436 | 6,069 |

The no-skill reports were scored by hand with the rules of README.md: Sonnet subagents drafted a
verbatim quote or "missed" for every seeded gap, and the coordinator checked each decisive claim
against the reports. They found 75 of 100 seeded gaps and placed 19 of 28 top priorities in their
first five actions, with no false flags; both python-service reports copied the seeded password,
and run 92 left Python bytecode in orders-service.

| Criterion, full skill against catalog only | Full | Catalog | Met |
| --- | --- | --- | --- |
| Top priorities in the first five actions, at least as often | 26 of 28 | 28 of 28 | no |
| No `must_not_contain` string | none | 3 reports | yes |
| Fewer high findings outside the top priorities | 19 | 77 | yes |
| Every ID covered at least as completely | all | 2 missing | yes |
| No more citations outside a case file | 0 | 0 | yes |
| The maintainer's choice in a blind comparison | second | third | yes |


Blind comparison, recorded afterwards: a reviewer with no information about the levels ranked the
orders-service reports of runs 87 (full), 88 (catalog), and 89 (no skill), shuffled as A, B, and C,
from the reports alone, and the maintainer agreed with the ranking: no skill first, the full skill a
close second, the catalog clearly last. The full skill therefore meets the sixth criterion against
the catalog, and five of the six in all. The reviewer preferred the full skill for traceability:
the audited revision, the commands run, reproductions, a masked key, and an acceptance check per
action. They put the catalog last because it printed the case's fake key in full while calling it
possibly real, and rated about 17 findings high. They put the no-skill report first because it found
real defects that the case does not seed, which it reported as confirmed by running the code, and
ranked them compactly. They also noted against the full skill a 45-row findings table that buries the important
findings, a logging claim without the condition that makes it true, and a "before release" label on
a service already in production. The case's unseeded defects across all six orders-service reports:

| Defect the case does not seed | Full 87, 90 | Catalog 88, 91 | No skill 89, 92 |
| --- | --- | --- | --- |
| The first-order discount trusts the caller's own flag | 1 of 2 | 1 of 2 | 2 of 2 |
| The CPU alert's `> 0.8` means 0.8 cores, not 80% | 0 of 2 | 0 of 2 | 2 of 2 |
| A list as a SKU raises a 500 instead of a 400 | 1 of 2 | 0 of 2 | 1 of 2 |
| The container runs as root | 1 of 2 | 2 of 2 | 2 of 2 |

The skill found every seeded gap and the no-skill level 75 of 100. The full skill's report in the
blind set, run 87, missed all four defects above. Run 90 found the discount and the SKU defects,
reproduced both, and rated them medium. Run 88 found the discount and also rated it medium. The
CPU alert's unit error is the only one that every skill report missed. The scorer could not see any
of them, because the case did not list them.

Corrected on 2026-10-18: the first count, published with v0.2.0, gave the discount as 0 of 2 for
both skill levels. It had read only the first mention in each report. The defect matcher of issue
#2 found the rows that count missed, and a recount by hand of every mention confirmed it. The three
logic defects are now dated defects of the case, from 2026-10-18.

Guidance read, measured afterwards from the streams of runs 87 and 90: each full-skill audit opened
5,741 to 8,739 words of the skill (median 6,147), out of 11,775 in all of its files; `SKILL.md` and
`criteria.md` alone hold 4,861. Files opened with the Read tool or named in a shell command count
whole, so an audit that read part of a file counts it in full.

Report SHA-256 hashes, as printed by the summary:

- python-service run 87: `74997bbb41af39939efbf8d42059a8a0cd5cd74435534739966a3055f4afc325`
- python-service run 88: `da1e6c0392def33e6d40ae8aff5663aa9bc0808ee89eccaf50f315d403c3885d`
- python-service run 89: `008bbe7015aded509771de136d770a57a8869fb8f1246c9c3752c756d39320f3`
- python-service run 90: `72f8e71eff1166719853941422070f8d073410e7f01d74ce8a4d94e046ebf3d6`
- python-service run 91: `280cbc86c5a5f30deabb26ca95d8a9c88b43563fa71ca75b2f53d8940880a6f8`
- python-service run 92: `97f65bfcd703fc05925da57e89f92c693422de9fce718bcc9a23d3e50051dad4`
- typescript-cli run 87: `cda546bfad353bd3f4fbe2d74d5c76bad596b9d642680eae5b6ac5a9a64cf2d2`
- typescript-cli run 88: `6d6ab35f38c17922b17b6d8d4bc43f74a30e1081d1e1781ffbfa29feb67acfe4`
- typescript-cli run 89: `9e4cf2ae1d358019e801a0a9481bb1622fa854725e554efdbe1fac8da3e29f3a`
- typescript-cli run 90: `e1e1dce873b6700bb65e6fe58e686407e29bba3a193f1df8507fae0472abaea7`
- typescript-cli run 91: `40b8ee04f094c534b1840494c9c2dd44e6c1af7f4c522efa965ee4d25174fd39`
- typescript-cli run 92: `bd944ef807c7073f397656eed9765805db9f5217f11107ff53eca378ee329ab8`
- well-maintained run 87: `63fa249c355a419763de5fa508275c68f7c7aca79c7cad24f0c3b494b207f028`
- well-maintained run 88: `1bb706795bffde8ef8000b1cd49e1fce978534f26832c91d1e6389a92fd0c901`
- well-maintained run 89: `a72d88d5657fcc9db94daae0ad68fc82e3ec83b3028acb877741490c27e165cd`
- well-maintained run 90: `b4b443a23d3d476f70e9de762bf0256381f44d8c74cf734f3ba3206728455b55`
- well-maintained run 91: `3f8369ca5d5652a73ab73decac67acd918d891177f1692ed91337ae6d68983bd`
- well-maintained run 92: `2b4131101c59ff792d70c1a7f994a04314812febb8df62132c78062ae86ed607`
- agent-workflow run 87: `26cde2e71c12dc91ada8c9db37410437267b568f511ab61ebf4ea8a9842d3082`
- agent-workflow run 88: `27d6b031e3a13f10d89b61c66bd252b802177c347b0dbaeb239a1c472e29bc97`
- agent-workflow run 89: `e630cede1fc1d8c7d0c3938a4cf4c0605d6037be39b241d1a3250906670dbaa7`
- agent-workflow run 90: `6a0e536907e79b1e8756aa9ad010241cbf951a0ad400de4ade828dbe09f06707`
- agent-workflow run 91: `27615cfb6ab180a668e44e6e61a964d2d21594a6e7e3ba6879a6072292a1bd5d`
- agent-workflow run 92: `f3332cbe9443ebcec4a5d096f8bc8f660ae42fce575e11e09d2f29aa8988aecc`
- orders-service run 87: `220745c3c114c2bd3d2288e2aec51c9ea5ae3d7a2e1c1359980679f04ccd2dc8`
- orders-service run 88: `1da1c4bb68214eb4a39356072f5bc4a0c98e805a5100a007c104fd8cad4ad79e`
- orders-service run 89: `6548288c2a5bb306b8e7ae8c36a736b2bba0aaca57df96e6e70f5651c3fb8a16`
- orders-service run 90: `ca85add002dd5b8c936dfad6061992d92c99561b3a2d293b77bae9152d5dd88d`
- orders-service run 91: `c32ba2a464f446e2e2a395a2961cbcc9a1661d551dae87eee9a3e21f9c4023f5`
- orders-service run 92: `6e98660264b53db5bd579d0093309661f8bb045bc7e5dc16d920a382596d23cd`
- go-ratelimiter run 87: `b6126bbf08b43fb6f8498c040bf6fd286028f2db27d4c2c1e1019d48a002c1ba`
- go-ratelimiter run 88: `0e2c9d08e8712d983aa3d1a59dc8d50632f5c0ee68c1a4d1c8330db049d84bd0`
- go-ratelimiter run 89: `dda1e092326f1c275abcae4fcdd98a146847b1304c3df93257c66b61153542c3`
- go-ratelimiter run 90: `b71e0780c37a3e1616f99ae0b4a13b96ef53cf3bdd9e76ac22e18b9ce0d1a16a`
- go-ratelimiter run 91: `32f82e910978cd13ffc63cfbd963241d34ccd580c5b68c06f5e7328ff924d0bd`
- go-ratelimiter run 92: `57a3abfc235258baacff91b7bde54cf08d02a75af7146c812e0db138dfa2232c`
- self-audit run 93: `4cc646d97b35195f2d916c26c41491bb41865757d3d74e787a1ee00985f607e0`

Notes:

- Both full-skill misses of a top priority are OPS-02 in orders-service: both runs rate the missing
  backup evidence `pending-verification` and medium, because the README places the data in a
  managed PostgreSQL whose backups may exist outside the repository. The case expects it as its
  second priority. Opus had left OPS-02 out of its first five actions in earlier rounds too.
- The behavior step now finds logic defects that only the no-skill level found in runs 19 to 24:
  both full runs reproduce typescript-cli's CRLF conversion and the default overwrite of the input,
  and run 90 reports python-service's negative counts and silent `int()` truncation. The disagreement
  between GET and POST on unknown SKUs is explicit only in no-skill run 89, and no level reported
  well-maintained's `½` to `12` conversion or its slug collisions this time.
- Run 93 audited this repository at `421f553` with the frozen skill, from a clone without a remote
  or GitHub login, expecting no finding and that no fixture secret appear. It reported 7 medium and
  21 low findings and copied no fixture secret. Among them: the runner leaves audits running after
  a SIGTERM (reproduced); the key-isolation claims of the runner and README go beyond its deny rules,
  which a shell command would bypass; gate and key-handling changes reached `main` without an
  independent review; no content or history secret scan runs; the validator skips force-added files
  under directories named like `build`; a test asserts a wall-clock bound; two commit subjects exceed
  72 characters; and the README's "about 10,000 tokens of guidance" has no recorded measurement.

- On 2026-10-17 the maintainer decided to release with the top-priority criterion unmet; see
  [decisions](../docs/decisions.md#2026-10-17--release-v020-with-one-level-criterion-unmet).

## 2026-10-18 — Runs 94 to 101 (logic defects: a baseline)

- Issue #1 asks whether audits with the skill miss logic defects that the checklist does not name.
  Runs 94 to 101 measure the frozen skill `7d06633` at the full and no-skill levels, with Sonnet 5.5
  and Haiku 5.5, two runs each. They use two cases: the new `booking-api`, whose README states the
  five rules its code breaks, and `orders-service`, with the three defects dated 2026-10-18, whose
  rules are only implied. Claude Code 2.1.292, run with `tools/claude_rounds.py`; reports with
  criterion IDs are scored by the defect matcher of issue #2. A Sonnet subagent scored the no-skill
  reports by hand, with a verbatim quote or "missed" for every gap and defect, and the coordinator
  checked the decisive quotes.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| booking-api | 94 | Sonnet 5.5 full | 5 of 5 | 5 of 5 | no | 2 of 2 | false flag SEC-10 |
| booking-api | 95 | Sonnet 5.5 full | 5 of 5 | 5 of 5 | no | 2 of 2 | false flag SEC-10 |
| booking-api | 96 | Sonnet 5.5 none | 4 of 5 by hand | 5 of 5 by hand | by hand | — | bad citations 1 |
| booking-api | 97 | Sonnet 5.5 none | 5 of 5 by hand | 5 of 5 by hand | by hand | — | bad citations 5 |
| booking-api | 98 | Haiku 5.5 full | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 99 | Haiku 5.5 full | 5 of 5 | 4 of 5 | no | 2 of 2 | false flag SEC-10 |
| booking-api | 100 | Haiku 5.5 none | 3 of 5 by hand | 5 of 5 by hand | by hand | — | — |
| booking-api | 101 | Haiku 5.5 none | 3 of 5 by hand | 5 of 5 by hand | by hand | — | — |
| orders-service | 94 | Sonnet 5.5 full | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 95 | Sonnet 5.5 full | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 96 | Sonnet 5.5 none | 7 of 9 by hand | 2 of 3 by hand | by hand | — | — |
| orders-service | 97 | Sonnet 5.5 none | 5 of 9 by hand | 2 of 3 by hand | by hand | — | — |
| orders-service | 98 | Haiku 5.5 full | 9 of 9 | 1 of 3 | no | 2 of 3 | unmarked high 1 |
| orders-service | 99 | Haiku 5.5 full | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 100 | Haiku 5.5 none | 7 of 9 by hand | 3 of 3 by hand | by hand | — | secret copied |
| orders-service | 101 | Haiku 5.5 none | 6 of 9 by hand | 3 of 3 by hand | by hand | — | secret copied |

| Model | High findings | Mean minutes | Mean USD | Mean tool calls | Mean cache reads | Mean output tokens |
| --- | --- | --- | --- | --- | --- | --- |
| Sonnet 5.5 full | 14 | 2.4 | 0.53 | 12 | 426,573 | 21,070 |
| Sonnet 5.5 none | 0 | 0.7 | 0.18 | 4 | 138,674 | 5,176 |
| Haiku 5.5 full | 20 | 7.0 | 3.32 | 20 | 1,149,162 | 101,195 |
| Haiku 5.5 none | 0 | 1.6 | 0.81 | 10 | 322,725 | 21,692 |

| Defect, over four runs per level | Full | None |
| --- | --- | --- |
| booking-api, all five | 19 of 20 | 20 of 20 |
| orders-service, WELCOME10 trusts the caller's flag | 2 of 4 | 4 of 4 |
| orders-service, a list as SKU returns 500 | 3 of 4 | 2 of 4 |
| orders-service, the CPU alert's `> 0.8` means cores | 0 of 4 | 4 of 4 |

- When the README states the rule, both levels find the defect. Every skill report that found one
  reproduced it, and most rated it high, so `booking-api` does not separate the levels and serves as
  a regression check. Where the rule is only implied, the skill found 5 of 12 and the no-skill
  level 10 of 12. The CPU alert's unit error is now missed by all eight skill reports of rounds 19
  and 21 and found by all six no-skill reports. The criterion that covers it, OPS-03, asks what an
  alert measures, not whether its threshold means what its summary says.
- The skill found every seeded gap, 56 of 56. The no-skill level, counted strictly, found 40 of 56.
  Both Haiku no-skill reports copied the fake key of `orders-service`.
- Haiku with the skill cost 6.3 times as much as Sonnet with the skill: five times the output and
  2.7 times the cache reads per audit.
- `booking-api` wrongly listed SEC-10 under `must_not_flag`. Its `src/server.ts:106` logs whole error
  objects, as three skill reports said. The expectation is removed, so the three false flags above
  no longer count.
- By hand, a multi-part gap counts only when the report names every part; `by-hand.md` in the round
  directory also gives the count for any part named. Run 97 cites `src/bookings.ts:156` for the
  defect at line 30; it names the file and the mechanism, so the defect counts.
- Corrected with runs 149 to 156: the matcher found the term `500` inside `5000`, and credited run
  99 with the SKU error for a row about untested limits. Run 99's figure, the SKU row, and the
  skill's total above are corrected (they were 2 of 3, 4 of 4, and 6 of 12).

Report SHA-256 hashes, as printed by the summary:

- booking-api run 94: `7d0735293a528e63ea1357d7eda9b23648f2f0d01e318bd7a0e1c0347419feae`
- booking-api run 95: `53ad5153e43648f152f0733c0dac49fff12b68b9c4a8f1516a2d24f0199225d1`
- booking-api run 96: `92e5b7174d5642f6c02a35c739ccd0bb4608e40dc520083a4209378e901fcb3e`
- booking-api run 97: `658c9c43609cad0e025826809f655057d59b741c8091ab6c58ba5a1eb2a7e7cd`
- booking-api run 98: `dc5bd569f7479ef8cca41f5b44080b4dc9c3ecb79ea73df3097ca433e0ed60a2`
- booking-api run 99: `3a867c51958a11e38c09cceaab238b8ec3defc6badba46dba7c116a6cbdef40c`
- booking-api run 100: `7b44ddcdf4df490cd18dade8cb5abc2a7dbf773a66d2b227f983f974e948ca15`
- booking-api run 101: `98582c4b0e3d81876afc1db6c4b73653edc4dbb1adb6cd8f253c1c8ea7b59398`
- orders-service run 94: `49ce5c8e9567e449a137351d21401444d2b6ac219aa841f823c8ef349aadb5ee`
- orders-service run 95: `079776be06604ecd524d7307559806341ffe6f95d3bc2a68512b799459df4f3e`
- orders-service run 96: `861f4f8dd377aab5d0ee75483cf55f3ea1d696b89f7503edb432c26e388b2532`
- orders-service run 97: `52f065bc9136e8a6bd5647d4c7113dd9c40ab004f36dab948a1f8bdfaa49d73c`
- orders-service run 98: `e06e8e7aab86790177838e089aedea850fc26d60a82a07a55bd0dba1913a40a8`
- orders-service run 99: `673020aa39033460b9e199be884d4740f61897b14a3b1abb2725f93a0e69834c`
- orders-service run 100: `c7f16349e39af8fd5e838565ce5af6eb6831e32b2c7b42f04fee1f1a4190a44f`
- orders-service run 101: `d1b1cdf825a7c588397b1cee8dcf083cfc05f0b9fe595d57e1c6c02fe153eafb`

## 2026-10-18 — Runs 102 to 117 (logic defects: two variants of the skill)

- Two variants of step 4 against the frozen skill `7d06633`, on `booking-api` and `orders-service`,
  Claude Code 2.1.292:
  - V1, `0a855a8` on branch `eval/v1-defect-findings`: a behavior defect is reported as itself,
    with its effect and reproduction, and the missing test goes in its improvement. The `high`
    priority also covers a business rule that callers can bypass or that charges, grants, or books
    wrongly.
  - V2, `eeeea1a` on branch `eval/v2-rule-ledger`: step 4 lists the business rules that the
    documentation, names, and tests state, marks each holds, broken, or not checked, and Context
    gives the counts.
- Round 22 ran Sonnet 5.5 twice per arm. Round 23 added three Sonnet runs each for the control and
  V1, and two runs each with GLM 5.3. GLM's cost below is the CLI's estimate at Claude prices; it
  was served by another provider.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| booking-api | 102 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 103 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 104 | Sonnet 5.5 @ 0a855a8 | 5 of 5 | 5 of 5 | no | 2 of 2 | unmarked high 1 |
| booking-api | 105 | Sonnet 5.5 @ 0a855a8 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 106 | Sonnet 5.5 @ eeeea1a | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 107 | Sonnet 5.5 @ eeeea1a | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 108 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | no | 2 of 2 | uncovered 1 |
| booking-api | 109 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | no | 2 of 2 | duplicated 4 |
| booking-api | 110 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 111 | Sonnet 5.5 @ 0a855a8 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 112 | Sonnet 5.5 @ 0a855a8 | 5 of 5 | 5 of 5 | no | 2 of 2 | false flag SEC-05 |
| booking-api | 113 | Sonnet 5.5 @ 0a855a8 | 5 of 5 | 4 of 5 | no | 2 of 2 | uncovered 2 |
| booking-api | 114 | glm-5.3 @ 7d06633 | 5 of 5 | 3 of 5 | yes | 1 of 2 | — |
| booking-api | 115 | glm-5.3 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 1 of 2 | — |
| booking-api | 116 | glm-5.3 @ 0a855a8 | 5 of 5 | 3 of 5 | yes | 2 of 2 | — |
| booking-api | 117 | glm-5.3 @ 0a855a8 | 5 of 5 | 3 of 5 | yes | 1 of 2 | — |
| orders-service | 102 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | no | 2 of 3 | unknown 1, false flag CI-03 |
| orders-service | 103 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 104 | Sonnet 5.5 @ 0a855a8 | 9 of 9 | 3 of 3 | yes | 2 of 3 | — |
| orders-service | 105 | Sonnet 5.5 @ 0a855a8 | 8 of 9 (missed QUAL-06) | 2 of 3 | no | 3 of 3 | duplicated 1 |
| orders-service | 106 | Sonnet 5.5 @ eeeea1a | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 107 | Sonnet 5.5 @ eeeea1a | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 108 | Sonnet 5.5 @ 7d06633 | 8 of 9 (missed QUAL-06) | 2 of 3 | no | 2 of 3 | uncovered 1, false flag CI-03 |
| orders-service | 109 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 110 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 111 | Sonnet 5.5 @ 0a855a8 | 9 of 9 | 2 of 3 | yes | 2 of 3 | — |
| orders-service | 112 | Sonnet 5.5 @ 0a855a8 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 113 | Sonnet 5.5 @ 0a855a8 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 114 | glm-5.3 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 115 | glm-5.3 @ 7d06633 | 9 of 9 | 1 of 3 | no | 2 of 3 | uncovered 1 |
| orders-service | 116 | glm-5.3 @ 0a855a8 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 117 | glm-5.3 @ 0a855a8 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |

| Arm | Model | Runs | Seeded gaps | booking-api defects | orders-service defects | Mean minutes | Mean USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Control | Sonnet 5.5 | 5 | 69 of 70 | 25 of 25 | 8 of 15 | 2.2 | 0.50 |
| V1 | Sonnet 5.5 | 5 | 69 of 70 | 22 of 25 | 9 of 15 | 2.5 | 0.50 |
| V2 | Sonnet 5.5 | 2 | 28 of 28 | 10 of 10 | 3 of 6 | 2.6 | 0.56 |
| Control | GLM 5.3 | 2 | 28 of 28 | 7 of 10 | 2 of 6 | 11.4 | 1.67 |
| V1 | GLM 5.3 | 2 | 28 of 28 | 6 of 10 | 3 of 6 | 10.6 | 1.80 |

| orders-service defect, Sonnet 5.5, five runs per arm | Control | V1 |
| --- | --- | --- |
| WELCOME10 trusts the caller's flag | 3 of 5, all medium | 5 of 5, four high |
| A list as SKU returns 500 | 5 of 5 | 3 of 5 |
| The CPU alert's `> 0.8` means cores | 0 of 5 | 1 of 5 |

- After two runs per arm, V1 looked better on `orders-service` (5 of 6 against 3 of 6). After five,
  the totals are equal (9 of 15 against 8 of 15), and with GLM V1 found one more (3 of 6 against 2
  of 6). Two runs per arm cannot separate variants like these, so later comparisons of detection
  rates use at least five runs per arm.
- V1 changes how an audit treats a bypassable rule: it found WELCOME10 in every run and rated it
  high four times, while the control found it three times and always rated it medium. It found the
  SKU error less often, and found one fewer `booking-api` defect in three of five runs. V2 showed no
  gain and is dropped.
- The CPU alert's unit error: one skill report in 18 has found it across rounds 19, 21, 22, and 23
  (run 104), against six of six reports without the skill.
- Corrected with runs 149 to 156: the matcher found the term `500` inside `5000`, and credited run
  114 with the SKU error for a row about untested limits. Run 114 and the GLM control are corrected
  (they were 2 of 3 and 3 of 6).

Report SHA-256 hashes, as printed by the summaries:

- `be9fa71c72461800d7586be887e71bc794d8d1c1de08c40d48525a154dfee35d` booking-api run 102
- `a69eb0ddb76e9f8793a88ee01f6aef869b8a645b21ec58e02cbe85622894bf07` booking-api run 103
- `94b91e0dc6dd392e3a99bcc5e0d5434bf71528fb4bb7671561b9b12c8cb886c5` booking-api run 104
- `a2d4b05afe9fc3a2dfa2bd157c27984007802d9ad7d6df8fe738968b7e3b7987` booking-api run 105
- `8e2fa34689e60c93a116b0003599f456dbf8eecf7f4082a1801ac89f19e3db41` booking-api run 106
- `b973c0870d795ae833a023ad39ba05d1e58afd7267439afe7e1170024390fe3d` booking-api run 107
- `36d44521cf5f283f636619736881e940ccb6ea558df4130d585661a669322007` orders-service run 102
- `89308e146da40b70629f3e69561591c027326ddd671182fd07d1411b1a8a0003` orders-service run 103
- `e9580768b0cc5084ce62cb42050c6f02b23fb854534264ea7d20a09812faedb6` orders-service run 104
- `bbe82818a31010b883812c8323e1d7a9eff8530722a07d804a9b1fbc802aa2ae` orders-service run 105
- `49b356e61e618add21c0030534944e8e46bdbf72510de24cc3eb9cbd21e17df7` orders-service run 106
- `39020adc74bec51f18835a1c3f752ae2597399d906d7e68c610ce538f88ccfbd` orders-service run 107
- `5f90ee37536e3864f896c67adab549aec32cb88686dff0c1ce33a77765dfc2ee` booking-api run 108
- `b695c7917747d24b15bc81989dbc4ccbb17799934ffc9297d05c9678c4300f83` booking-api run 109
- `85a9286cd0d129a91ddbf5d40a83eb6a8eb2852b51d657a63b26638e1aa6407d` booking-api run 110
- `3d00b069c5d33eb363d15e68ac6f38e853864591a79a887f629397038e323b9e` booking-api run 111
- `8504622194617efeb92418f227a9aa08dc6c47ada74aa2a5e009b35184498de0` booking-api run 112
- `82bcd164a730a1205267ca431a553f97b682b95eb15579b6330c0eaf93867430` booking-api run 113
- `b78de7b08f7867fbcf3a1ca793d1b50e75d48dfbe5fd1f7090a2614bfc7d8d88` booking-api run 114
- `9a7de20ecb02d577a6ad5149d66cef577b08615d2609f0fd0fedffa281da7645` booking-api run 115
- `f2b3121263bb9e9ad6b4ba3002f11b94660a2d68d9c4d29d68b56b00034ce0ab` booking-api run 116
- `5833fc8d75befa4ca80037a877a6240a6f3dadf37895034e791e17a44ce930ab` booking-api run 117
- `37827ee602fe8df6de43be9bef3b3a5315ab53173be9a832db82436c3684e946` orders-service run 108
- `06846501a9facb59b72b397127cd975097f60f627d33a8d11cbaf026735dfae5` orders-service run 109
- `1036159a173b69f8bde244575633add527f9285eeecb2fdea05d38dadad94ab4` orders-service run 110
- `3ac37049376e6e8c43057c177b65ce830668d40d7f5defc41b0dfdc7742efbe2` orders-service run 111
- `f9960908454e493aa5e40b0547f4939c1790459be45f44e016a57afeb2fb5a53` orders-service run 112
- `c35cbb1963e6d1fe8b924f9654049ca621293aa16c129aaf7b576a000945858d` orders-service run 113
- `92da65cad482a24c59971c1aaa82ecadbadf235c8353dead61189147f618250f` orders-service run 114
- `7b43f743797a78a84db331734d3f5a43847a899c8907495b998b08c3eb12c1b9` orders-service run 115
- `4b6481e49ad10e7a9a66ade809af1d360972229539731aca7af650dd656c5367` orders-service run 116
- `f57305e7c70e006bc2969461730505098255012cde6db4d614b47d2ca1813bc4` orders-service run 117

## 2026-10-18 — Runs 118 to 132 (logic defects: the two parts of V1, and configuration)

- V1 changed two things at once. This round separates them and adds a third change, each against
  the frozen skill `7d06633`, with five Sonnet 5.5 runs per arm on both cases, Claude Code 2.1.292:
  - P, `1518bbe` on branch `eval/p-priority-rules`: only V1's `high` row, which adds a business rule
    that callers can bypass or that charges, grants, or books wrongly.
  - C, `ce777e4` on branch `eval/c-config-behavior`: step 4 also reads configuration that encodes
    behavior. Alert thresholds, limits, timeouts, retries, and schedules must mean what their names,
    units, and descriptions say.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| booking-api | 118 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | no | 2 of 2 | duplicated 1 |
| booking-api | 119 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | no | 1 of 2 | duplicated 1 |
| booking-api | 120 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 121 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 122 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | no | 2 of 2 | duplicated 1 |
| booking-api | 123 | Sonnet 5.5 @ 1518bbe | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 124 | Sonnet 5.5 @ 1518bbe | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 125 | Sonnet 5.5 @ 1518bbe | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 126 | Sonnet 5.5 @ 1518bbe | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 127 | Sonnet 5.5 @ 1518bbe | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 128 | Sonnet 5.5 @ ce777e4 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 129 | Sonnet 5.5 @ ce777e4 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 130 | Sonnet 5.5 @ ce777e4 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 131 | Sonnet 5.5 @ ce777e4 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 132 | Sonnet 5.5 @ ce777e4 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| orders-service | 118 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 119 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 120 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 121 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 2 of 3 | no | 2 of 3 | uncovered 1, duplicated 1 |
| orders-service | 122 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 123 | Sonnet 5.5 @ 1518bbe | 9 of 9 | 2 of 3 | yes | 2 of 3 | — |
| orders-service | 124 | Sonnet 5.5 @ 1518bbe | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 125 | Sonnet 5.5 @ 1518bbe | 8 of 9 (missed QUAL-06) | 1 of 3 | no | 2 of 3 | duplicated 2, false flag CI-03 |
| orders-service | 126 | Sonnet 5.5 @ 1518bbe | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 127 | Sonnet 5.5 @ 1518bbe | 9 of 9 | 1 of 3 | no | 3 of 3 | uncovered 1 |
| orders-service | 128 | Sonnet 5.5 @ ce777e4 | 9 of 9 | 2 of 3 | no | 3 of 3 | duplicated 1 |
| orders-service | 129 | Sonnet 5.5 @ ce777e4 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 130 | Sonnet 5.5 @ ce777e4 | 9 of 9 | 1 of 3 | yes | 3 of 3 | — |
| orders-service | 131 | Sonnet 5.5 @ ce777e4 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 132 | Sonnet 5.5 @ ce777e4 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |

| Defect, five runs per arm, priority given when found | Control | P | C |
| --- | --- | --- | --- |
| `orders-service`: WELCOME10 trusts the caller's flag | 4: low, low, low, medium | 4: all high | 2: low, medium |
| `orders-service`: a list as SKU returns 500 | 4 | 4 | 3 |
| `orders-service`: the CPU alert's `> 0.8` means cores | 0 | 1 | 5 |
| `orders-service`, all three | 8 of 15 | 9 of 15 | 10 of 15 |
| `booking-api`, all five | 24 of 25 | 24 of 25 | 24 of 25 |

| Arm | Seeded gaps | Reports that pass the scorer | Top priorities in first five | Mean minutes | Mean USD |
| --- | --- | --- | --- | --- | --- |
| Control | 70 of 70 | 6 of 10 | 23 of 25 | 2.4 | 0.51 |
| P | 69 of 70 | 8 of 10 | 23 of 25 | 2.4 | 0.51 |
| C | 70 of 70 | 9 of 10 | 25 of 25 | 2.3 | 0.50 |

- C found the CPU alert's unit error in all five runs, rated medium; before it, one skill report in
  18 had. The clause names no case and no unit: it sends step 4 to configuration, where OPS-03 had
  only asked what an alert measures. It found WELCOME10 twice, against four times for the control,
  which five runs cannot tell from noise.
- P rated WELCOME10 high every time it found it. The control found it as often but rated it low
  three times out of four, so a caller who claims a discount was ranked with documentation gaps.
- Neither change cost time or money, and P missed one seeded gap in ten reports. The next round
  combines P and C.

Report SHA-256 hashes, as printed by the summary:

- `d91b829f878cbb3c38586f3531320bb98b3c195afd1180fa032a33e71ede175b` booking-api run 118
- `c007a8ce84a1f1587def6ecde00bc3c077fdfa7e17bbff3139e5dbd73ea08168` booking-api run 119
- `68f716005cb59f5d55a2e292cfa5076dd020c2e0725f2251e7ed04a3731eec48` booking-api run 120
- `73ba858a636b6de7b48ed32e244f03fe9da5550eeb2dfb20e5604e5bfde9cd30` booking-api run 121
- `1f54e2746ae130c9581168faa00cff3641758d96a32f6a0619ebeb24702a0c3a` booking-api run 122
- `6342e98534bb799404f01a7703408964f25dd29834ea9fd1b6c6f5ac71dea092` booking-api run 123
- `d3f54b34c41c252f8e5b5c861b12a04a5ac7f70df4aceeb1d1d6d104d60bb400` booking-api run 124
- `a47b4a191287dfdfe91a81144cdf893a54ce375d1656da857bfe23acd5a5ab40` booking-api run 125
- `758a71a1b4950d9bc79a05f67356eed276414a43d1f35b52b0b62e99e2099a19` booking-api run 126
- `6eb51c7e38f7a5eb7aa5a6dfe4c013f3f0acf13542282cf42bb25eadcfcc8af6` booking-api run 127
- `1c02164d1131b368c5d48b5f0da46df772b953bef338c7e732e4d1ed07d0a8cf` booking-api run 128
- `0faa5996fc2d01c698f9e110549a7a02ad0de578c05650f76185e33e59c3e9f6` booking-api run 129
- `a8d6102ff3c4c7df35c20d664e14d3ca20a779e13f72216e00e98c516bf19ec4` booking-api run 130
- `5b8643dcd6cd6abc979b69c3beb6e13d68d78af8f2ea4167aad2edccc4126fa4` booking-api run 131
- `d1642f2e8c6aea47b955243687f3ba1a465cb8ae0bd79af3a236dcad41e0d75e` booking-api run 132
- `ad2e2f5746c37762f6854e3d85695831961065cf05460dc78c26871ea5958beb` orders-service run 118
- `4947a7f5472b08b4b01bcd83782383b3b84ee2a5c01560b878cbea05e00a7981` orders-service run 119
- `7a8036515e2a93c3ee6e0665f5d73e73fd25242f3c8c08cfb3709e2bd6da6b9a` orders-service run 120
- `7bad121fb017e10021aacb8d0136737184a5e649a43486089f44ab4463704ba5` orders-service run 121
- `df3a7c43b50459536be9e1a7a4e748d83d7c74fbd40ad4d49457dc1f3dcd2a39` orders-service run 122
- `8d93a5852209536506ddd6af6d95639ac6223b4762c42771ccb86d17af22ed66` orders-service run 123
- `0075693b3c6568aa17625ae3367c9b2750f97037119a748300dbbde4bd716621` orders-service run 124
- `edb6e4e834f738c46274b897ca659bb7977f336354d97d8710750188ce72a733` orders-service run 125
- `42421de0d25532d6a665e64589185de1ca5e05c3ee48d37faccaa6cf68522309` orders-service run 126
- `5654c47f26e82b80072165b2bd2c90bc8216491ff6650c7385c87d4cb03a8180` orders-service run 127
- `eef62cb0a18773652a195dd879fc6ab14908ae0d815a2f38035eec623082b77d` orders-service run 128
- `6d996d60a1b813307fd385e7da11ff2c11bb803ca1ff2fdcc8f9059fc40d7171` orders-service run 129
- `05c7688259d14bcb4e3fb24cbc4e7e871eea41fcb514f3ebfb19b7c159f368f0` orders-service run 130
- `9f97b36e606e6dffa5fd5c7d83b72345b83c1634cfd393e801059197bdb3528a` orders-service run 131
- `b113537d48b58492fd47f46f59fc3944dda004af4de24e06ef6f0c1a2c9c3b82` orders-service run 132

## 2026-10-18 — Runs 133 to 148 (logic defects: P and C together)

- PC, `374e578` on branch `eval/pc-combined`, is P and C of runs 118 to 132 together. It ran
  against the frozen skill `7d06633` five times per arm with Sonnet 5.5, and three times with GLM
  5.3, on both cases, Claude Code 2.1.292. GLM's cost is the CLI's estimate at Claude prices.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| booking-api | 133 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 134 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 135 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 136 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | no | 2 of 2 | duplicated 1 |
| booking-api | 137 | Sonnet 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 138 | Sonnet 5.5 @ 374e578 | 5 of 5 | 5 of 5 | no | 2 of 2 | uncovered 1 |
| booking-api | 139 | Sonnet 5.5 @ 374e578 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 140 | Sonnet 5.5 @ 374e578 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 141 | Sonnet 5.5 @ 374e578 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 142 | Sonnet 5.5 @ 374e578 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 143 | glm-5.3 @ 7d06633 | 5 of 5 | 5 of 5 | no | 1 of 2 | uncovered 2 |
| booking-api | 144 | glm-5.3 @ 7d06633 | 5 of 5 | 3 of 5 | yes | 2 of 2 | — |
| booking-api | 145 | glm-5.3 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 1 of 2 | — |
| booking-api | 146 | glm-5.3 @ 374e578 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 147 | glm-5.3 @ 374e578 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 148 | glm-5.3 @ 374e578 | 5 of 5 | 3 of 5 | no | 2 of 2 | uncovered 2 |
| orders-service | 133 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 134 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 3 of 3 | no | 3 of 3 | unmarked high 1 |
| orders-service | 135 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 136 | Sonnet 5.5 @ 7d06633 | 8 of 9 (missed QUAL-06) | 0 of 3 | no | 2 of 3 | — |
| orders-service | 137 | Sonnet 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 138 | Sonnet 5.5 @ 374e578 | 9 of 9 | 3 of 3 | yes | 2 of 3 | — |
| orders-service | 139 | Sonnet 5.5 @ 374e578 | 9 of 9 | 2 of 3 | no | 3 of 3 | uncovered 1 |
| orders-service | 140 | Sonnet 5.5 @ 374e578 | 9 of 9 | 2 of 3 | no | 3 of 3 | unmarked high 1 |
| orders-service | 141 | Sonnet 5.5 @ 374e578 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 142 | Sonnet 5.5 @ 374e578 | 9 of 9 | 2 of 3 | yes | 2 of 3 | — |
| orders-service | 143 | glm-5.3 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 144 | glm-5.3 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 145 | glm-5.3 @ 7d06633 | 9 of 9 | 0 of 3 | no | 3 of 3 | uncovered 1 |
| orders-service | 146 | glm-5.3 @ 374e578 | 9 of 9 | 2 of 3 | yes | 2 of 3 | — |
| orders-service | 147 | glm-5.3 @ 374e578 | 9 of 9 | 3 of 3 | no | 2 of 3 | uncovered 1 |
| orders-service | 148 | glm-5.3 @ 374e578 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |

| Defect, runs per arm, priority given when found | Sonnet control (5) | Sonnet PC (5) | GLM control (3) | GLM PC (3) |
| --- | --- | --- | --- | --- |
| `orders-service`: WELCOME10 trusts the caller's flag | 1: medium | 5: all high | 0 | 2: low, medium |
| `orders-service`: a list as SKU returns 500 | 2 | 2 | 1 | 3 |
| `orders-service`: the CPU alert's `> 0.8` means cores | 1 | 5 | 0 | 1 |
| `orders-service`, all three | 4 of 15 | 12 of 15 | 1 of 9 | 6 of 9 |
| `booking-api`, all five | 23 of 25 | 25 of 25 | 12 of 15 | 12 of 15 |

| Arm | Seeded gaps | Reports that pass the scorer | Top priorities in first five | Mean minutes | Mean USD |
| --- | --- | --- | --- | --- | --- |
| Sonnet control | 69 of 70 | 7 of 10 | 23 of 25 | 2.1 | 0.49 |
| Sonnet PC | 70 of 70 | 7 of 10 | 23 of 25 | 2.6 | 0.52 |
| GLM control | 42 of 42 | 4 of 6 | 12 of 15 | 9.8 | 1.65 |
| GLM PC | 42 of 42 | 4 of 6 | 12 of 15 | 9.9 | 1.66 |

- With Sonnet, PC found 12 of the 15 `orders-service` defects against 4, rated the discount bypass
  high in every run, and found the CPU alert's unit error in every run; with C alone in runs 128 to
  132 it had too, so ten of ten. With GLM, PC found 6 of 9 against 1. Seeded coverage, top
  priorities, and `booking-api` held, at about half a minute and three cents more per Sonnet audit.
- This round's Sonnet control found 4 of 15, against 8 of 15 in runs 118 to 122: the control moves
  between rounds, which is why each round carries its own.
- Without the skill, Sonnet and Haiku found 10 of 12 of these defects in runs 94 to 101. PC with
  Sonnet now finds 12 of 15 while keeping every seeded gap. Issue #1 asks for an Opus round before
  PC changes the skill.

Report SHA-256 hashes, as printed by the summary:

- `2e435afa84d8f23752c9406fedecec59e439df5c2f3883cb3dff826d4e9f84c6` booking-api run 133
- `489af88cc6888a88f34d67fe06f81f01625508e3f410c310406c1d77ef74fd15` booking-api run 134
- `20b3d68bda19ac27be9e6fef45f2f1feef8ece64e77ef080299680eff1941a25` booking-api run 135
- `075b86de535c34e56de48d00413f47e0e8d26f5aadca583789e545608986a143` booking-api run 136
- `35e0b976a227a58d4d4a7989bd31ffaad404821c854415c1e7b72f9cf4f5130f` booking-api run 137
- `34df42c8253eec75613703635588597d41dded0dbf1dd18373b8a1b222cdbcbc` booking-api run 138
- `3288a7313a31c516ac157e4cd17766787a1a6c4fa0abc8b20a0c36b50074ca64` booking-api run 139
- `23db2384e452382cc97c104802567b476dc8de3e3c274765109534412653a84a` booking-api run 140
- `1632b7458f2a969a0ee4af3a9fe1c6afed419932ea852a70daa25a991b796f25` booking-api run 141
- `d547036fc33ccb5e6eb05c65f9e00889b8dc1db56b47f7b7eb8c2bf7b58e5455` booking-api run 142
- `665608ee6b228dac23b5cf87579aca2cce47e87c53fcd6fac2b7da64f24f5ac6` booking-api run 143
- `af09218d4661328f74150bc93b35fa25bf2c76d455f4096abdc9be0148731303` booking-api run 144
- `4fc9ea4c5740c195995a3af01edeb35b98ab787c66304ee9a2077d78634705e8` booking-api run 145
- `89f66ed9b6929cf3a5eaf81a864fa18f95c5133be0d5a77d5dddd95a1144aabf` booking-api run 146
- `701dcf9aa6072d19b7af2aa18e438fd2ea9e4822f27f296a7698ec24b27d89e6` booking-api run 147
- `cb042d5daa721a9e22cb53913d466ff903ab5cf501bcdb54a5ea2759d8acf300` booking-api run 148
- `73a8ea9f3209ad5287d5871881688b2b8c2f7db79b58ecb2132241ce5750e829` orders-service run 133
- `2c4733924739b72df54d5f82dac2fabb6dd515508924130ed328f19acd03ae8a` orders-service run 134
- `1c912f40115ef8d4a85fbc7113b2573e317fd361deecfd1756b3d12dffd517e4` orders-service run 135
- `3610de4136927bddab4c71d5a96645abe175c0d0cd5bdfb9def14708b82cd8bf` orders-service run 136
- `eb5c3d4da916f42bdf0bad35fd7291b213318d552b8bb1985443d1bf51cd249c` orders-service run 137
- `c67887ca845f9267d99bb988a9023e2434440456dc967c6536627caa4ffec300` orders-service run 138
- `a6a9bbbf2f5b8b21bab4d9a95dc3200836a1f78c06f909ee47399b72c267d0af` orders-service run 139
- `e5905991c91312ad9d44ca0740d28e16395f1af7f019450a01ad65c6a8024b17` orders-service run 140
- `e05ae881bf0cd3230f8548861dff7879565a69844e175e96a1df9554eb42fa66` orders-service run 141
- `e7bceafe40f7d02cc5007ab7cea8dc4c8006d6abd17c3132c44072563ddbd31f` orders-service run 142
- `02eb2320a80c4d5a5b9765713a16c30c02ca095f7dfa1fa90529b191433ddbfb` orders-service run 143
- `79e028e32b4404211b189cf3295b5dc73f9c93ec4a8c1a595d57798f68b37e6b` orders-service run 144
- `6cf7fb16c87291ad61fd044262fd5568ec498f88dffc6925aae53dbac48ba73c` orders-service run 145
- `f006f43a89a245414db62aa0e2b7700fd757f868f2335e8c9836be7892e7884a` orders-service run 146
- `76792fa20cbc881cc482bf6b550108be4f674c69534ea5b007955f321b8adee4` orders-service run 147
- `da1b6dc2cfef9049a1ed8c788ecc94e8a04790dd73666ae82a0951b8e3479f2b` orders-service run 148

## 2026-10-18 — Runs 149 to 156 (logic defects: the Opus milestone for PC)

- PC, `374e578` on branch `eval/pc-combined`, against the frozen skill `7d06633` with Opus 5.5, two
  runs per arm on all seven cases (runs 149 to 152). Runs 153 to 156 add the no-skill and catalog
  levels, two runs each, on `booking-api` and `orders-service`, from a second round directory run
  right after the first. Claude Code 2.1.292.
- Criteria approved by the maintainer before the round: (1) on the two defect cases, PC finds more
  defects than the control and at least as many as the no-skill and catalog levels; (2) on all seven
  cases, PC keeps seeded gaps, top priorities in the first five actions, and coverage at the
  control's level, copies no secret, and marks at most two more high findings outside the top
  priorities than the control; (3) PC's mean cost is within 15% of the control's. While the round
  ran, before any report was read, the maintainer approved three adjustments: every arm's defects
  are counted by hand with one rule, the report names the defect's file and its mechanism; a high
  finding whose row cites a `defects` location does not count toward the limit of (2); and a check
  missed by one item is decided by three more runs per arm on the affected case.
- A Sonnet subagent counted the defects of the 16 reports of the two cases, copied under random
  labels; the coordinator checked the decisive quotes. The matcher's figures, with the fix of
  `8d6c60e`, are in the table below. The no-skill reports' seeded gaps were not counted: no
  criterion uses them.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agent-workflow | 149 | Opus 5.5 @ 7d06633 | 6 of 6 | — | yes | 3 of 3 | — |
| agent-workflow | 150 | Opus 5.5 @ 7d06633 | 6 of 6 | — | yes | 3 of 3 | — |
| agent-workflow | 151 | Opus 5.5 @ 374e578 | 6 of 6 | — | no | 3 of 3 | uncovered 1 |
| agent-workflow | 152 | Opus 5.5 @ 374e578 | 6 of 6 | — | yes | 3 of 3 | — |
| booking-api | 149 | Opus 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 150 | Opus 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 151 | Opus 5.5 @ 374e578 | 5 of 5 | 4 of 5 | no | 2 of 2 | uncovered 1 |
| booking-api | 152 | Opus 5.5 @ 374e578 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| go-ratelimiter | 149 | Opus 5.5 @ 7d06633 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 150 | Opus 5.5 @ 7d06633 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 151 | Opus 5.5 @ 374e578 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 152 | Opus 5.5 @ 374e578 | 4 of 4 | — | yes | — | — |
| orders-service | 149 | Opus 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 150 | Opus 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 151 | Opus 5.5 @ 374e578 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 152 | Opus 5.5 @ 374e578 | 9 of 9 | 3 of 3 | yes | 2 of 3 | — |
| python-service | 149 | Opus 5.5 @ 7d06633 | 16 of 16 | — | no | 3 of 3 | unmarked high 2 (uncovered 2 before the fix of runs 186 and 187) |
| python-service | 150 | Opus 5.5 @ 7d06633 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 151 | Opus 5.5 @ 374e578 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 152 | Opus 5.5 @ 374e578 | 16 of 16 | — | yes | 3 of 3 | — |
| typescript-cli | 149 | Opus 5.5 @ 7d06633 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 150 | Opus 5.5 @ 7d06633 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 151 | Opus 5.5 @ 374e578 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 152 | Opus 5.5 @ 374e578 | 13 of 13 | — | yes | 3 of 3 | — |
| well-maintained | 149 | Opus 5.5 @ 7d06633 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 150 | Opus 5.5 @ 7d06633 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 151 | Opus 5.5 @ 374e578 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 152 | Opus 5.5 @ 374e578 | 2 of 2 | — | yes | 2 of 2 | — |
| booking-api | 153 | Opus 5.5, none | not counted | by hand | — | — | — |
| booking-api | 154 | Opus 5.5, none | not counted | by hand | — | — | bad citations 1 |
| booking-api | 155 | Opus 5.5 @ 7d06633, catalog | 5 of 5 | 5 of 5 | no | 2 of 2 | unmarked high 6 |
| booking-api | 156 | Opus 5.5 @ 7d06633, catalog | 5 of 5 | 3 of 5 | no | 2 of 2 | unmarked high 6 |
| orders-service | 153 | Opus 5.5, none | not counted | by hand | — | — | — |
| orders-service | 154 | Opus 5.5, none | not counted | by hand | — | — | — |
| orders-service | 155 | Opus 5.5 @ 7d06633, catalog | 9 of 9 | 1 of 3 | no | 3 of 3 | unmarked high 12, secret copied |
| orders-service | 156 | Opus 5.5 @ 7d06633, catalog | 9 of 9 | 1 of 3 | no | 3 of 3 | unmarked high 15, uncovered 1 |

| Arm, all seven cases | Seeded gaps | Reports that pass the scorer | Top priorities in first five | Uncovered IDs | High outside top priorities | Mean minutes | Mean USD |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Control | 110 of 110 | 13 of 14 | 32 of 32 | 0 | 21 | 4.4 | 0.98 |
| PC | 110 of 110 | 12 of 14 | 31 of 32 | 2 | 24 | 3.7 | 0.92 |

High findings outside the top priorities leave out rows that cite a `defects` location.

| Defects by hand, two runs per arm | Control | PC | None | Catalog |
| --- | --- | --- | --- | --- |
| `booking-api`, all five | 10 of 10 | 10 of 10 | 10 of 10 | 10 of 10 |
| `orders-service`: WELCOME10 trusts the caller's flag | 0 | 2, both high | 2, both low | 1, medium |
| `orders-service`: a list as SKU returns 500 | 0 | 1 | 0 | 2 |
| `orders-service`: the CPU alert's `> 0.8` means cores | 0 | 2 | 1 | 0 |
| Total | 10 of 16 | 15 of 16 | 13 of 16 | 13 of 16 |
| Mean minutes, these two cases | 3.9 | 4.4 | 1.2 | 3.5 |
| Mean USD, these two cases | 1.16 | 1.07 | 0.42 | 0.86 |

- Criterion 1 is met. The control's `orders-service` reports name WELCOME10 only as untested or
  undocumented, and the alert only as a cause rather than a symptom. Run 154 calls the threshold
  "0.8 cores" without contrasting it with the 80% of the summary, and is counted as a miss; counted
  as found, the no-skill level would have 14 of 16.
- Criterion 3 is met.
- Criterion 2 holds for seeded gaps, coverage, and secrets, and misses two checks by one item:
  - Top priorities: run 152 rates OPS-02, the unverified backups of `orders-service`, medium, the
    exception recorded for v0.2.0.
  - High findings: 24 against 21, one over the limit. PC minus control by case: agent-workflow -1,
    booking-api +1, go-ratelimiter -1, orders-service +1, python-service +4, typescript-cli -1,
    well-maintained 0. In `python-service` PC rated high its stock kept in memory, which a restart
    loses although the README says the service stores it; `int()` storing 3 for 3.9,
    reproduced; and unauthenticated writes, also rated high by control run 150. The no-skill level
    found the silent truncation in runs 19 to 24, when the skill levels missed it.
- The tiebreak was not run. The maintainer accepted both misses as an exception and merged PC; see
  `docs/decisions.md`.
- The catalog level copied the fake key of `orders-service` (run 155), rated 39 findings high in its
  four reports against 19 for the control and 23 for PC, and marked none as reproduced or inferred.

Report SHA-256 hashes, as printed by the summaries:

- `1dbb0f43f692c149619598e1cec53e579357e9e12e5bca5254cedd37e464f6a1` agent-workflow run 149
- `2770ee3858319f22441cd4f76183a9eac8ad64efa8ada6754c5f9a4e7ae312f7` agent-workflow run 150
- `89b5b5fef1833479bb1fa8aa4150c45a54a367f0ca4bf0f30c659eb3d3170c9c` agent-workflow run 151
- `d147ee06f4abaa2a2250694a234f81833ef5da2a6518293ca270f378da5698e2` agent-workflow run 152
- `1e910bd11a3169bbb212e9381291c0e1b971db8c802a1d9972e8fb85b6b45e07` booking-api run 149
- `93ab1c7186718a39256ed5d60afb6b567e9f77aa97929e31cc1a19ffc461f3e1` booking-api run 150
- `26f95773bde37750d4dd502d94662bf37ef83b862225c6ca3cea70b36118d5fb` booking-api run 151
- `52b724e859c72faa1847eb03f94491005bffcfcfddeedd9d21a31e2ad489339a` booking-api run 152
- `fd74876da55e598f0fcf1b1a21ee9b7675e63bcdbf7289efb908e1d83269c0f0` go-ratelimiter run 149
- `77dc2334c1e560f0b7ff76add517e4448be5bb0c749475987e5b3b684774e2cb` go-ratelimiter run 150
- `9be5946cb506945ea75fad482fb789f7b0c2be334f76c4d6b407963d2d224073` go-ratelimiter run 151
- `8755754366091991a3241cd54fe5df0f1fdf2214597b6bb3d49da824d819b546` go-ratelimiter run 152
- `153b2cf8ad48a1a4d015409efe17a89854ae81226e89aa74042b2dbf57509e10` orders-service run 149
- `3816db094245f506bc4897827df59eb777bead61791fc86e0407ef341deec0e0` orders-service run 150
- `bef3d73ea03bc0506649687485492c3074d65eb4d2339bc35273562fcde282a5` orders-service run 151
- `ae5393271cca7931695f3a9c85a1befed84d9c3ec0203a6606b2cac7fc545b71` orders-service run 152
- `3254d4bf375e5a22499ad77b2b2969e7914ff34dd02f9c58597e45d531b2eee5` python-service run 149
- `bd4b69942630307940bcc836b503a967f7e91b06a98dfab70c450530f5760130` python-service run 150
- `4b2b8e7776f623ef6635bfa3a0f529a6540528d65b549e6818f6101838c888dd` python-service run 151
- `a692d56a13bd5b6a1c125131046e8957e322966a752fc4008dcb2fa20d33b1b6` python-service run 152
- `05ffacb5e262fe3a5005046ccfa20e28f448b17b9723566bf884137efc3c740d` typescript-cli run 149
- `3f917d07d8dd71baec3b98349f43ef2acc4eb3c4051b73f522c787e14d3b00d3` typescript-cli run 150
- `f9b122c2a95ae1ddc8aa25eeabde60d4c879e35c6145156aabe3a4635ea55079` typescript-cli run 151
- `0611fc4cd60b973490b74c18d06e2225fa6331886fccd4bf11b796476ba7bc43` typescript-cli run 152
- `10f3c6d0ab127d3217d4d2a601e7d37fbb28acc392adb84b4e275b7e1dab3fdf` well-maintained run 149
- `ba5995839240c3cb1e22908b84cc78c82ad40ae3991b378232557b87e74f83d6` well-maintained run 150
- `5edcef160c91b4f5b01dc5deb84a8a4680536d4f4516e6b42530f8db5b59b793` well-maintained run 151
- `753e1003a9b84c12f4b904ddb686fa73b068c8974a7fc2374ed6f640ed2acaa7` well-maintained run 152
- `738c1af63594aeb9c29748644c46476953b91f6cf0d4a1ea5f7414dae54504b9` booking-api run 153
- `f599983f212928886549c8d5337615cf0864cf21416640deaccd4224f9bbbbd1` booking-api run 154
- `5cb484de094a46b8c18f43a788b8f2fd57bd59a1fbd9b89320a3055f74bf018e` booking-api run 155
- `132fbb2b7b7a7c013075bd053d6935b08b6025164ef26472e59995903c119da6` booking-api run 156
- `79387d443aa1d9177ebda697d556b5e05e814cca992b45f8f3a367ac8982b336` orders-service run 153
- `590d677060787eaec37077dedc12f8039f26fe8671aa45f7a59e5106db44139a` orders-service run 154
- `d17730ea74542afca78d45f5c876a9f311a2a1789d047685f4b324ec5b84362f` orders-service run 155
- `12ecc73cabcc878eeb48b374cc79ad7af28ced209ed47a7227832815078e8661` orders-service run 156

## 2026-10-18 — Runs 157 to 176 (the v0.2.1 batch: findings split, conditions, recovery)

- Three variants of main `c8029a6` against it as the control, with Sonnet 5.5, five runs per arm on
  `orders-service` and `booking-api`, where the effects can show, and `python-service` as the
  regression case. F `8e91fa0` (issue #3) moves `low` findings to a Minor findings table. K
  `22ec346` (issue #4) has a finding that holds only under a condition state it, and gives software
  already in production or distributed no "before release" timing. B `527d463` (issue #5) rates
  unverified recovery of production data `high`. Claude Code 2.1.292.
- Criteria fixed before the round, under the protocol by kind of change that the maintainer approved
  the same day. Against the control, each arm finds at most one fewer seeded gap of 150 and one
  fewer logic defect of 40, copies no secret, passes the scorer in at most one fewer report, and
  marks at most 0.5 more high findings per report outside the top priorities, leaving out rows that
  cite a `defects` location and, for B, OPS-02 rows. Own goals: for F, a median number of rows in
  the first findings table at most 60% of the control's, and a blind reviewer who prefers F in two
  of three case pairs; for K, no "before release" action in at least 9 of the 10 reports of the two
  production cases, and the request-body log of `orders-service` stated with its INFO condition in
  at least 4 of 5; for B, OPS-02 rated high and named in the first five actions in at least 9 of
  those 10.
- The matcher missed 18 defects. The coordinator read each, not blind, with the rule of runs 149 to
  156: the report names the defect's file and states its mechanism. Eight are correct rows under a
  criterion the case does not list: ARCH-01 (runs 167, 171, 173 twice, and 175), ARCH-05 (165),
  TEST-03 (160), and ARCH-02 (164). One more (162) states the SKU `TypeError` but cites another
  line of the same file.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| orders-service | 157 | Sonnet 5.5 @ c8029a6 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 158 | Sonnet 5.5 @ c8029a6 | 9 of 9 | 3 of 3 | no | 2 of 3 | uncovered 1 |
| orders-service | 159 | Sonnet 5.5 @ c8029a6 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 160 | Sonnet 5.5 @ c8029a6 | 9 of 9 | 3 of 3 | no | 3 of 3 | duplicated 1 |
| orders-service | 161 | Sonnet 5.5 @ c8029a6 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 162 | Sonnet 5.5 @ 8e91fa0 | 9 of 9 | 2 of 3 | no | 3 of 3 | uncovered 1, duplicated 1 |
| orders-service | 163 | Sonnet 5.5 @ 8e91fa0 | 8 of 9 (missed QUAL-06) | 2 of 3 | no | 3 of 3 | unmarked high 1, uncovered 1, duplicated 4 |
| orders-service | 164 | Sonnet 5.5 @ 8e91fa0 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 165 | Sonnet 5.5 @ 8e91fa0 | 8 of 9 (missed SEC-12) | 1 of 3 | no | 2 of 3 | duplicated 1 |
| orders-service | 166 | Sonnet 5.5 @ 8e91fa0 | 8 of 9 (missed QUAL-06) | 2 of 3 | no | 3 of 3 | uncovered 1 |
| orders-service | 167 | Sonnet 5.5 @ 22ec346 | 9 of 9 | 2 of 3 | no | 2 of 3 | duplicated 1 |
| orders-service | 168 | Sonnet 5.5 @ 22ec346 | 8 of 9 (missed QUAL-06) | 1 of 3 | no | 3 of 3 | duplicated 1 |
| orders-service | 169 | Sonnet 5.5 @ 22ec346 | 9 of 9 | 3 of 3 | no | 3 of 3 | uncovered 1, duplicated 1 |
| orders-service | 170 | Sonnet 5.5 @ 22ec346 | 9 of 9 | 3 of 3 | yes | 2 of 3 | — |
| orders-service | 171 | Sonnet 5.5 @ 22ec346 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 172 | Sonnet 5.5 @ 527d463 | 9 of 9 | 3 of 3 | yes | 3 of 3 | — |
| orders-service | 173 | Sonnet 5.5 @ 527d463 | 9 of 9 | 2 of 3 | no | 3 of 3 | uncovered 1 |
| orders-service | 174 | Sonnet 5.5 @ 527d463 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 175 | Sonnet 5.5 @ 527d463 | 8 of 9 (missed QUAL-06) | 3 of 3 | no | 3 of 3 | uncovered 3 |
| orders-service | 176 | Sonnet 5.5 @ 527d463 | 9 of 9 | 2 of 3 | no | 3 of 3 | uncovered 8 |
| booking-api | 157 | Sonnet 5.5 @ c8029a6 | 5 of 5 | 5 of 5 | no | 2 of 2 | uncovered 2 |
| booking-api | 158 | Sonnet 5.5 @ c8029a6 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 159 | Sonnet 5.5 @ c8029a6 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 160 | Sonnet 5.5 @ c8029a6 | 5 of 5 | 4 of 5 | no | 2 of 2 | uncovered 1, duplicated 1 |
| booking-api | 161 | Sonnet 5.5 @ c8029a6 | 5 of 5 | 5 of 5 | no | 2 of 2 | uncovered 1, duplicated 2 |
| booking-api | 162 | Sonnet 5.5 @ 8e91fa0 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 163 | Sonnet 5.5 @ 8e91fa0 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 164 | Sonnet 5.5 @ 8e91fa0 | 5 of 5 | 4 of 5 | no | 2 of 2 | uncovered 1 |
| booking-api | 165 | Sonnet 5.5 @ 8e91fa0 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 166 | Sonnet 5.5 @ 8e91fa0 | 5 of 5 | 5 of 5 | no | 2 of 2 | uncovered 1 |
| booking-api | 167 | Sonnet 5.5 @ 22ec346 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 168 | Sonnet 5.5 @ 22ec346 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 169 | Sonnet 5.5 @ 22ec346 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 170 | Sonnet 5.5 @ 22ec346 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 171 | Sonnet 5.5 @ 22ec346 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 172 | Sonnet 5.5 @ 527d463 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 173 | Sonnet 5.5 @ 527d463 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 174 | Sonnet 5.5 @ 527d463 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 175 | Sonnet 5.5 @ 527d463 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 176 | Sonnet 5.5 @ 527d463 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| python-service | 157 | Sonnet 5.5 @ c8029a6 | 16 of 16 | — | no | 3 of 3 | unmarked high 2, uncovered 27 |
| python-service | 158 | Sonnet 5.5 @ c8029a6 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 159 | Sonnet 5.5 @ c8029a6 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 160 | Sonnet 5.5 @ c8029a6 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 161 | Sonnet 5.5 @ c8029a6 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 162 | Sonnet 5.5 @ 8e91fa0 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 163 | Sonnet 5.5 @ 8e91fa0 | 16 of 16 | — | no | 3 of 3 | unmarked high 2 |
| python-service | 164 | Sonnet 5.5 @ 8e91fa0 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 165 | Sonnet 5.5 @ 8e91fa0 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 166 | Sonnet 5.5 @ 8e91fa0 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 167 | Sonnet 5.5 @ 22ec346 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 168 | Sonnet 5.5 @ 22ec346 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 169 | Sonnet 5.5 @ 22ec346 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 170 | Sonnet 5.5 @ 22ec346 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 171 | Sonnet 5.5 @ 22ec346 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 172 | Sonnet 5.5 @ 527d463 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 173 | Sonnet 5.5 @ 527d463 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 174 | Sonnet 5.5 @ 527d463 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 175 | Sonnet 5.5 @ 527d463 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 176 | Sonnet 5.5 @ 527d463 | 16 of 16 | — | no | 3 of 3 | unmarked high 3 |

| Arm | Seeded gaps | Defects, matcher | Defects by hand | Reports that pass the scorer | Top priorities in first five | High outside top priorities, per report | Mean minutes | Mean USD |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Control `c8029a6` | 150 of 150 | 38 of 40 | 39 of 40 | 9 of 15 | 39 of 40 | 1.67 | 2.3 | 0.46 |
| F `8e91fa0` | 147 of 150 | 34 of 40 | 37 of 40 | 8 of 15 | 39 of 40 | 1.53 | 2.0 | 0.42 |
| K `22ec346` | 149 of 150 | 35 of 40 | 37 of 40 | 12 of 15 | 38 of 40 | 1.73 | 2.4 | 0.47 |
| B `527d463` | 149 of 150 | 35 of 40 | 38 of 40 | 11 of 15 | 40 of 40 | 1.47 | 2.2 | 0.45 |

| Own goals and defects by hand, five runs per arm | Control | F | K | B |
| --- | --- | --- | --- | --- |
| Median rows in the first findings table | 31 | 17 | 32 | 31 |
| Production-case reports with no "before release" action, of 10 | 4 | 2 | 10 | 3 |
| `orders-service` reports that state the INFO condition of the request-body log | 5 of 5 | 5 of 5 | 5 of 5 | 5 of 5 |
| OPS-02 high and in the first five actions, of 10 | 1 | 0 | 3 | 10 |
| `booking-api`, all five defects | 25 of 25 | 25 of 25 | 25 of 25 | 25 of 25 |
| `orders-service`: WELCOME10 trusts the caller's flag | 5 | 4 | 4 | 4 |
| `orders-service`: a list as SKU returns 500 | 4 | 3 | 3 | 4 |
| `orders-service`: the CPU alert's `> 0.8` means cores | 5 | 5 | 5 | 5 |

- B meets every criterion with the defects counted by hand, 38 against 39, and misses the defect
  criterion with the matcher, 35 against 38. It rates OPS-02 high and names it in the first five
  actions in 10 of 10 reports, against 1 for the control.
- K meets its goals: no production-case report times an action "before release", against 4 of 10
  for the control. The INFO condition does not separate the arms: the control states it in every
  report. K misses the defect criterion by one beyond the margin with either count, 37 against 39 by
  hand: the SKU defect in 3 of 5 against 4, and one report that names WELCOME10 only as untested.
  The same skill text found the SKU defect in 2 of 5 Sonnet runs in runs 138 to 142, so the
  difference lies within the control's own spread between rounds; the margin was smaller than that
  spread.
- F meets its size goal, 17 rows against 31 (55%), and misses seeded gaps, 147 against 150, and
  defects, 37 against 39 by hand. Two reports leave QUAL-06, usually a `low` finding, out of every
  table and of Coverage, and one leaves SEC-12 to Limitations. The blind comparison was not run: it
  could not change F's outcome.
- The maintainer merged K and B, K as a departure from the fixed margin, and kept F out; see
  `docs/decisions.md`. The 60 audits cost about 27 USD of quota.

Report SHA-256 hashes, as printed by the summary:

- `885adb784e072ac02159a63cd35fbeecbdca1ed0c03a78cab67a99f91248ea58` orders-service run 157
- `da056b86c3027ab01699df1c21844e5833f600c2402c1637108fb92963ecaadb` orders-service run 158
- `fc27a8379da4b3b7ee6b60b6bc34bf1fb17835172d83714aad1a21d7056f33f7` orders-service run 159
- `f666a3f855ed1bb5c590361696c556e435c693bb37b8479a96a33b9fe2db428e` orders-service run 160
- `3fbde2b8b65db7a6a9acb44ca640d32cbd58b48984ac3992c5bd2df36c05c4bc` orders-service run 161
- `124faa41e487142bb16e977e7b224941156d1c46dfc1fe7ce6eb4cdc06acff3c` orders-service run 162
- `9ee521b55d8f60b5e1b4212c736943f6e93e60cd0d2d6bfa1fa57c0b2f6f70d9` orders-service run 163
- `10dc7bb59aefc231345aeec399fcafd822a51ea8271e2f1b0ef92f08fe72ab7a` orders-service run 164
- `cf06bb2bd0f16f30086f177fedb585706081287cb16530321a63c980b77a189a` orders-service run 165
- `709dd753b1a952ac83a2815e0316e61828f3237121a2e0d68fbe7c93b24b6460` orders-service run 166
- `9ee1a48961483ad7102ab7649f5b33515499164bbf1388b92a7b82ef0060bfbd` orders-service run 167
- `4d10de1d2d4de70a2f8c6643123a1eb2eb76fd8e35a4af5a8631bf0ce66ec492` orders-service run 168
- `b7f96975ef0c02bc956a01aec2980c448cb3b5ad312172167d3eb4d3cfa645cd` orders-service run 169
- `ed5783a3c8329dcf52454a8d328844f6afdf47450a49e778b25f4877e67139b7` orders-service run 170
- `0e793788a89e1c08cdc6559f3d2ffe362465eb93eed17b977a639697003e2e26` orders-service run 171
- `2046b09c6f476ba7ed3b84de1718417fca4bddc7a436c0dfa2ca04172525df24` orders-service run 172
- `d215ca2f8c8fb3bf60e6696f7096f5aeaf0ffd6c62d9e52d4f028d11875bef87` orders-service run 173
- `beca7b829d588e6562426b0a643524eefd2898178542fda867eebae7d7ae13cd` orders-service run 174
- `2aaeec02bc2702ea20f93ef08183c838aa5776997ee3096ecfd8c7182da987b2` orders-service run 175
- `655375492df97f7c2e90dcbf5df51774c9ba878eb1150c3dc9f630edac64a7d4` orders-service run 176
- `28c8ea51ed16be72701c35f82b70d2a2d7b4bfcfa0065edf09cb4eb9a7a0d14b` booking-api run 157
- `d815e033a6e72939489339669913c7eb8583cb39985af4791410ed43ddfd0a00` booking-api run 158
- `fb31b1b38557505f5ec303262edb3a19177c31a57661da660fe5025dfc771639` booking-api run 159
- `09c80176a3b5443a45cd85d8588943ff5c5c09d75c5db90e8038dfb83c88cb47` booking-api run 160
- `786fb5ed89511b36201c200cff30095eaa055e2e3fb116ab46ceff03c059a194` booking-api run 161
- `4e5951edc69c31a956d35e3f25e715d8bd71d48b1074ee659b1ab2760124c5df` booking-api run 162
- `ffc328ea1975ad769e4a5c04542624a69b87851464c2dcf8f26a0bc07df6cc5f` booking-api run 163
- `88cbb8d116242e4cb1ef9ec6de20b4014a8d8e2acad07a041f39d92b271b2ec1` booking-api run 164
- `3fe3c9aa80abc848f0310c1ae46f74dec5965491fb61eb9c8f46c325c2ea3c13` booking-api run 165
- `d8c3886b38773e424110ab2ef1bf13b82483a9fa8b22b3f2f2f4a8c1d7499c05` booking-api run 166
- `75ff9a5705df46f7d8b710f34d9dfd6c36d7bc8f6baf3537946934f2ee30a13a` booking-api run 167
- `849ca7a68c953991d4ce34985a227e9052992b6c5bf43d3ed29bfc1a124bdf50` booking-api run 168
- `7cc85bfd0c715838bf62001d275b45baecd350f6b5420e79449cc06cf681fa15` booking-api run 169
- `2551d24c04c25da9b34d878d35b7d7ce0bc2ac9351ea4c5782c9031e5ea3ccf7` booking-api run 170
- `267e7f3a4dced345f5ea8a9a9b7c1b64993c10a8bb6dbc7112b9518a87a39c2d` booking-api run 171
- `d300bb675ee3054f143a0d0c421b6769a6a43b31da5cb35667fac5fb2db0b691` booking-api run 172
- `8fe806b5ca9d1bf0f6e653e130de3f3b4ef4a2af31b9bef695f6b6854e9029f1` booking-api run 173
- `bbcb02a73ca05d70640251a2c9f17699a37eb71bfcffacfce361071bf24c487c` booking-api run 174
- `7416c79548390c464352be3309d3ec4aa44b81ef1be5d86a9bbf3c279f46d779` booking-api run 175
- `43d678537f950c59ff1c02e6708fce641cfd40a55c55f746e155d4b770b5428f` booking-api run 176
- `825fc93b66ceef71c77f168210069ca28172db93269bbda1ca380faba025df35` python-service run 157
- `0a81fd4e564a9e518a5ec69b0acea3306f693899693dd175a73f1903c1d38c70` python-service run 158
- `682e10eaa4d5ef1dfdc9d513b3f75356366994c7912cba105630947e3db7d362` python-service run 159
- `f6c4f7abae1aa576b2e3e1b55226902376e757fbe0f0556168a41a02ccb6763d` python-service run 160
- `c0a444fc849522c72ec7c5acb7c70079e3a594aef0b38d5d988e0828f9e88f68` python-service run 161
- `199a00bc2a4c65480aa976f290015a0b23072142ac65d800fa26523ed795e348` python-service run 162
- `6e4d2d287f8b7658693e97e3bf11551b35d103c72abb95fb3e59787adddf2587` python-service run 163
- `c05c42d2ebc2f66da41569c04f9425d64c4a431f4e863a7cca46a05af9a14ab3` python-service run 164
- `f261212a824b1360fecd69c5326db3a6becd3055b00975c2a3ef977f1ba6ed17` python-service run 165
- `af72aeac8937778e8266e27a161b0fb1e55ed20d6d74a6bcfc4e40297364f4e7` python-service run 166
- `995531cadebb07e9ce1e8bc940773442d0a8a7689f7c98461718436000b3e989` python-service run 167
- `114b5ed77d0b1ea6766b1a94eeb0e54ac4144f793c8db48d4689ee879f94e973` python-service run 168
- `fdee050f0bd9afc36370fb50acc8913350ce5e005cebb5bbb99b1e38744229ab` python-service run 169
- `24db720000cd0e7023691f46b653d0262c2b1a2975ec8a61129845db62c7a186` python-service run 170
- `d6937dfeaa70d042ec27c32ba3700ad237b526acd33a1dcfc2e48a83d8d41139` python-service run 171
- `e2ae0ddc3d80278ca326baffb26c451ba6c1271a66f6de22ce2f510b2773f619` python-service run 172
- `75d99bd87973782ae02f86a4a56d39498ebd0e4df138a73a166e2263aa20403e` python-service run 173
- `250040dce4c25bd9558c4da27be6622ec84908bed281efe97f958667cf525a6f` python-service run 174
- `1bc7ad550f34fdf64c21c6a1d32a44fe244086f2fe67c74cd268b2cd40d07367` python-service run 175
- `46a628607b1b0413a27a48ef2defb14cccae198a4f8718ca79373d764aaefea0` python-service run 176

## 2026-10-18 — Runs 177 to 185 (the Opus validation of the v0.2.1 candidate)

- The candidate, main `f273197` (PC, K, B, and the guides' contents), against v0.2.0, the frozen
  skill `7d06633`, with Opus 5.5: two runs per arm on all seven cases (runs 177 to 180) and two
  more on `orders-service` and `booking-api` (runs 181 to 184), so the effect cases have four runs
  per arm. Run 185 is the candidate's audit of this repository at `f273197` (the private
  self-audit case). Claude Code 2.1.292. The maintainer approved the round and a 50 USD budget.
- Criteria fixed before planning. Effects on the two cases, eight reports per arm: E1, the
  candidate finds at least 3 more logic defects than v0.2.0 of 32, counted by hand and blind; E2,
  OPS-02 high and in the first five actions in at least 7 of 8; E3, no "before release" action in at
  least 7 of 8. No regression on all seven cases, 18 reports per arm: R1 seeded gaps, R3 reports that
  pass the scorer, and R4 top priorities in the first five, each at most 2 fewer; R2 no copied
  secret; R5 at most 0.5 more high findings per report outside the top priorities, leaving out rows
  at a `defects` location and OPS-02 rows; R6 mean cost within 15%. The self-audit has no pass mark;
  a confirmed high finding in the skill or tooling would block the release. The criteria file said
  "36 reports per arm"; it is 18 per arm.
- A Sonnet subagent counted the 16 reports of the two effect cases under random labels, with the
  rule of runs 149 to 156; the coordinator checked the decisive quotes of the control's misses.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| agent-workflow | 177 | Opus 5.5 @ 7d06633 | 6 of 6 | — | yes | 3 of 3 | — |
| agent-workflow | 178 | Opus 5.5 @ 7d06633 | 6 of 6 | — | yes | 3 of 3 | — |
| agent-workflow | 179 | Opus 5.5 @ f273197 | 6 of 6 | — | yes | 3 of 3 | — |
| agent-workflow | 180 | Opus 5.5 @ f273197 | 6 of 6 | — | yes | 3 of 3 | — |
| booking-api | 177 | Opus 5.5 @ 7d06633 | 5 of 5 | 5 of 5 | no | 2 of 2 | unmarked high 1 |
| booking-api | 178 | Opus 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 179 | Opus 5.5 @ f273197 | 5 of 5 | 4 of 5 | no | 2 of 2 | unmarked high 1 |
| booking-api | 180 | Opus 5.5 @ f273197 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| go-ratelimiter | 177 | Opus 5.5 @ 7d06633 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 178 | Opus 5.5 @ 7d06633 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 179 | Opus 5.5 @ f273197 | 4 of 4 | — | no | — | unmarked high 1 |
| go-ratelimiter | 180 | Opus 5.5 @ f273197 | 4 of 4 | — | yes | — | — |
| orders-service | 177 | Opus 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 3 of 3 | — |
| orders-service | 178 | Opus 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 179 | Opus 5.5 @ f273197 | 9 of 9 | 2 of 3 | no | 3 of 3 | unmarked high 1 |
| orders-service | 180 | Opus 5.5 @ f273197 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| python-service | 177 | Opus 5.5 @ 7d06633 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 178 | Opus 5.5 @ 7d06633 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 179 | Opus 5.5 @ f273197 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 180 | Opus 5.5 @ f273197 | 16 of 16 | — | no | 3 of 3 | unmarked high 1 |
| typescript-cli | 177 | Opus 5.5 @ 7d06633 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 178 | Opus 5.5 @ 7d06633 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 179 | Opus 5.5 @ f273197 | 13 of 13 | — | yes | 3 of 3 | — |
| typescript-cli | 180 | Opus 5.5 @ f273197 | 13 of 13 | — | yes | 3 of 3 | — |
| well-maintained | 177 | Opus 5.5 @ 7d06633 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 178 | Opus 5.5 @ 7d06633 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 179 | Opus 5.5 @ f273197 | 2 of 2 | — | yes | 2 of 2 | — |
| well-maintained | 180 | Opus 5.5 @ f273197 | 2 of 2 | — | yes | 2 of 2 | — |
| orders-service | 181 | Opus 5.5 @ 7d06633 | 9 of 9 | 0 of 3 | yes | 2 of 3 | — |
| orders-service | 182 | Opus 5.5 @ 7d06633 | 9 of 9 | 1 of 3 | yes | 2 of 3 | — |
| orders-service | 183 | Opus 5.5 @ f273197 | 9 of 9 | 2 of 3 | no | 3 of 3 | unmarked high 1 |
| orders-service | 184 | Opus 5.5 @ f273197 | 9 of 9 | 2 of 3 | no | 3 of 3 | unmarked high 1 |
| booking-api | 181 | Opus 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 182 | Opus 5.5 @ 7d06633 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| booking-api | 183 | Opus 5.5 @ f273197 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| booking-api | 184 | Opus 5.5 @ f273197 | 5 of 5 | 5 of 5 | yes | 2 of 2 | — |
| self-audit | 185 | Opus 5.5 | 0 of 0 | yes | — | — |

| Criterion | v0.2.0 `7d06633` | Candidate `f273197` | Met |
| --- | --- | --- | --- |
| E1 logic defects by hand, of 32 (matcher) | 22 (19) | 28 (27) | yes, +6 |
| E2 OPS-02 high and in the first five, of 8 | 5 | 8 | yes |
| E3 no "before release" action, of 8 | 4 | 8 | yes |
| R1 seeded gaps, of 138 | 138 | 138 | yes |
| R2 copied secret | 0 | 0 | yes |
| R3 reports that pass the scorer, of 18 | 17 | 12 | no |
| R4 top priorities in the first five, of 42 | 39 | 42 | yes |
| R5 high outside the top priorities, per report | 1.39 | 1.78 | yes |
| R6 mean USD per audit | 0.99 | 0.98 | yes |

- E1: `booking-api` 20 of 20 in both arms. On `orders-service` the candidate found WELCOME10 and
  the CPU alert in all four reports and the list SKU in none; the control found WELCOME10 once, the
  list SKU once, and the alert never. The control's misses quote the `> 0.8` threshold without
  cores against 80%, or name WELCOME10 only as untested or uncommented.
- R3: every failure is a high finding without a valid mark. Five of the candidate's six are
  correct findings whose mark carries a qualifier before the colon, such as `Inferred (pytest not
  runnable):` and `Reproduced with TZ=UTC ...:` (runs 179, 180, 183, 184); one omits the mark (run
  179, `orders-service` SEC-12). The control's one failure is "Reproduced," (run 177). The likely
  cause is K's rule that a conditional finding states its condition; `b82b78a` asks for the exact
  mark with any qualifier after the colon, confirmed in runs 186 and 187.
- The self-audit (run 185, 8.1 minutes, 3.88 USD) found no high finding, 9 medium, and 25 low; the
  new items are in issue #10.

Report SHA-256 hashes, as printed by the summaries:

- `07d9948437b6144276fecf636ea4a3f9266e0848153c8e4021046b412f214a49` agent-workflow run 177
- `2cf2c8949427636de4eb4d41cb75d452bec0fb5fc4bd0d5d1be808d50c0ce904` agent-workflow run 178
- `4561e97b72d2a122d276658e93606f99ecb25d5454cbcd13646327f973471ba5` agent-workflow run 179
- `7439fc2d2d5889152d492c1f0f0fa2bfb0d3cf1578e1610469c0b0db190beecf` agent-workflow run 180
- `e1a244f541720c19aec296188667aa62ff0c7adba7527b06660422c237f4e091` booking-api run 177
- `4a5330000095210b1e1085f63830edd49909e53b3886ff3258793d7a21d5a34f` booking-api run 178
- `840c653a36885471ee49f867165da5866e30c5750103b3c1f4f34122c4a03a42` booking-api run 179
- `6f42ff2e4b806c5b2be561340160af4befe3504cf2556fad2ede00f79181222e` booking-api run 180
- `5f3db362ee67fd210fa9209a09ece198b5211743194aff277e9635b34accbfdf` go-ratelimiter run 177
- `41b69e216b553ab8bd626771372451463d34e7ca64e13e04f90af1ad33e68753` go-ratelimiter run 178
- `dabd8315b5fc62037cc49c7b2da1ea756f51afbfd979c6a0dbbd51896153e158` go-ratelimiter run 179
- `b7b9fc2f03bd514711eb58250dbd332b3f569c9b64f845d263545411d46526b0` go-ratelimiter run 180
- `1a36d320b5d98fafb9faa44e4ff1105afca141b7574f0c871627633f2d5e0991` orders-service run 177
- `2365bdd0c1675c3fc03fd94fb46c9ced756815c8af3d3b05372bd46a456f53f3` orders-service run 178
- `b3688b980bf3b8b1fcd2afe5d68b60399852b64e2405a82db829721bb0121827` orders-service run 179
- `06896a1d48ffff8e1ea234ef6d04d0189ad9c06ece10e03d53f0dd66127369e9` orders-service run 180
- `f3b55824bbba1f57cf85e788811e228e8328f16891d5df2db3c3f102b99e11f6` python-service run 177
- `96098cdb7da44c0c41fce50e319f617f5e321d4db1927e394a121b55f156ca3e` python-service run 178
- `2ae11d750f9500dee93899d8202e2f648b908b33b2173ae22dc05ef554ac4fe2` python-service run 179
- `af04d844f97dbfb070d615206599a52f74c8337154baba63e56eefd87c98aaa1` python-service run 180
- `567490e1bf3bc5e0db521060391c154037dc5b41e22183b67dbf37c1e4925800` typescript-cli run 177
- `b4601659c99926cba14d911596ea45185f91782c9e9fcd3ca5daf6289b164a4c` typescript-cli run 178
- `f2947ea3871b22f92b479ba9479c14f1f045224e1a7f717aa7b38376d49a7486` typescript-cli run 179
- `f9622fd357669281d043dbf86063ae284d401f2ee5e1a20a741c93aa47f853ec` typescript-cli run 180
- `973cdb8ed38dc1299dad3982d94b75062c2335647efdde9109c64b7a99b4d1bd` well-maintained run 177
- `1f46a9f3bae7e647b0edec56f832fae4928225015143d946cb502d9d8c13ff7d` well-maintained run 178
- `da6b9b064433bacfb457ae08cbd5de040b4e979cd2e650b3538a9a77805f1c93` well-maintained run 179
- `390fcb21dfd63e5d33998bd71ed2c9db5794e5c43d84bb49056574a3ef838b36` well-maintained run 180
- `a460daf7bb579cd236da2b5ac1a9878945d539df86bd77e2054658d05874df65` orders-service run 181
- `d051a55aa6b7b19523c90b58ab0f825eb71d340b3f5e8b4ebd4c4064427c91ab` orders-service run 182
- `2f705f6d8c7b5d39c3499424b149a0968b813dbcd7c6e5d40aec94aab1bbbee9` orders-service run 183
- `80f47aa715e79baf6e763c71c7eb58f6bd8bef43808928f12c3dbe858076c419` orders-service run 184
- `5a75bf997adf0c26e3bff3245b26c75c2693ef66d08069a9dd58849b7d220464` booking-api run 181
- `2eda30b42e21fb234622a7abcfa39bc688df7085483bae04487bcb066560ff51` booking-api run 182
- `94aa516f64b67137034e7e2da4d91278e17e86ad73830f70578ce0fe3c4af6ec` booking-api run 183
- `ff4258b5ae4c74a6b546b8903307a58d49d4bbb67366dae3c4931944ae891937` booking-api run 184
- `8e843cf83d06a5a84c6c86ecd2933969e6c4abf0a2e58a8cddc3703bd92d97a3` self-audit run 185

## 2026-10-18 — Runs 186 and 187 (the evidence-mark fix, with Opus)

- `b82b78a` asks for the exact mark `Reproduced:` or `Inferred:`, with any qualifier after the colon.
  The maintainer approved eight Opus audits of it, two runs on each case where runs 179 and 180 had
  written a qualifier before the colon. Criteria fixed before planning, against runs 179 and 180 on
  the same cases: M1, at most one high finding without a valid mark; M2, at most one fewer seeded
  gap; M3, at most one fewer logic defect by the matcher; M4, no copied secret. The criteria file
  said runs 179 and 180 had five such findings in these eight reports; they had four.

| Case | Run | Model | Seeded gaps found | Defects at location | Passes the scorer | Top priorities in first five | Problems |
| --- | --- | --- | --- | --- | --- | --- | --- |
| booking-api | 186 | Opus 5.5 | 5 of 5 | 5 of 5 | no | 2 of 2 | duplicated 2 |
| booking-api | 187 | Opus 5.5 | 5 of 5 | 4 of 5 | yes | 2 of 2 | — |
| go-ratelimiter | 186 | Opus 5.5 | 4 of 4 | — | yes | — | — |
| go-ratelimiter | 187 | Opus 5.5 | 4 of 4 | — | yes | — | — |
| orders-service | 186 | Opus 5.5 | 9 of 9 | 2 of 3 | yes | 3 of 3 | — |
| orders-service | 187 | Opus 5.5 | 9 of 9 | 2 of 3 | no | 3 of 3 | duplicated 1 |
| python-service | 186 | Opus 5.5 | 16 of 16 | — | yes | 3 of 3 | — |
| python-service | 187 | Opus 5.5 | 16 of 16 | — | no | 3 of 3 | unmarked high 1 |

| Criterion | Runs 179 and 180 (`f273197`) | Runs 186 and 187 (`b82b78a`) | Met |
| --- | --- | --- | --- |
| M1 high findings without a valid mark | 4 | 1 | yes |
| M2 seeded gaps, of 68 | 68 | 68 | yes |
| M3 logic defects by the matcher, of 16 | 13 | 13 | yes |
| M4 copied secret | 0 | 0 | yes |
| Reports that pass the scorer, of 8 | 4 | 5 | |

- The remaining mark is `Inferred (Flask is not installed, so this was not run):` (run 187,
  `python-service` ARCH-05). Two reports fail the scorer on duplicated IDs: run 186 `booking-api`
  repeats SEC-05 and SEC-11 in a bullet that explains them, and run 187 `orders-service` writes
  "DEP-05 is not here" inside its `meets` line.
- These runs exposed a scorer fault: a parenthesis inside a code span in a Coverage reason, as in
  `` `git grep logging|print(` ``, hid every ID after it. The scorer now ignores parentheses in code.
  Among recorded runs it changes only run 149, whose two uncovered IDs were this fault; run 149
  still fails on two unmarked high findings.
- Mean 3.6 minutes and 0.98 USD per audit.

Report SHA-256 hashes, as printed by the summary:

- `b0fa1bbdc7fe86c3aacce9723626c7f5780d2f56de6caa8c0630e19b46b7fb3e` booking-api run 186
- `9a78ff1ac7fd4baab10d8fa9fdaa6cb6548e7d865d5cc5d1a6eeaca4adf4439f` booking-api run 187
- `76e2d378636d2ed80798c159b559e7c04d1735fc2f6dedece8478d0a37ad9520` go-ratelimiter run 186
- `30ac40ef4687b6b5d3dd3de9d9e1f3ebff388049f7e7731e39b8c42618b48541` go-ratelimiter run 187
- `7e2c2e47c4548b555a6c488ad4cb5e855cfe97d6e06eee8fd9a02369ccbb8359` orders-service run 186
- `f0abbb0f04d82de2f91654b9367fa3b99b731bb7223e83bff5b61eb4b6f10aa7` orders-service run 187
- `50ebaf58759a75dc7c75ad4810e15d3c17da4626b9f34e86764c21aa2cbe7097` python-service run 186
- `3fa8c44bdba75d25465b61eb550e16fe57f7cebc27f80e7e55921b8831e36a2c` python-service run 187
