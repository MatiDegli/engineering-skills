# Maintaining engineering-skills

- Read README.md and CONTRIBUTING.md before changing anything; write repository content in English.
- Keep skills independent of any language, framework, or tool: state what to verify and why.
- Keep one explanation per rule: guides explain, criteria.md indexes checks, SKILL.md holds the procedure.
- Keep each skill self-contained; its links must stay inside its directory.
- Never renumber or reuse a criterion ID.
- After changing a skill, the criteria, or an evaluation case, run the cases and record the results.
- Distinguish recommendations from implemented controls and verified results.
- Check sources when changing recommendations; record the review's scope and date.
- On Windows, prefer WSL2 unless native behavior is required.
- Run `python3 tools/check.py`; when changing workflows or their validator,
  also run `bash tools/check_workflows.sh`. Report actual limitations.
- Justify policy changes separately and follow the commit policy in CONTRIBUTING.md.
- Publishing releases, rewriting history, and changing licenses require maintainer authorization.
