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
