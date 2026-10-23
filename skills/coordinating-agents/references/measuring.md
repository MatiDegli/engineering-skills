# Measuring a change

Read this when judging whether a change to a workflow, a skill, a prompt, or a routing choice
worked. Run-to-run variation in agent behavior is large, so a comparison needs a design.

- **Fix the criteria before the runs.** Write them in a file with the run records. They may change
  only before anyone reads a result, and the record says when the owner approved the change.
- **Run a control in the same batch.** The unchanged version runs beside the candidate, with jobs
  interleaved, because the control's own results move between batches.
- **Margins must exceed the noise.** The same text found one defect in 2 of 5 runs and, two rounds
  later, in 4 of 5. Derive each margin from the observed spread, or name a tiebreak in the criteria
  file before the runs. Two runs per arm show a direction, not a size; decide between close variants
  with about five.
- **Before paying for a tiebreak, ask what the doubt is about.** More runs answer a doubt about
  frequency. A doubt about whether results are right needs the results read.
- **A proxy criterion can punish the effect sought.** A measure of "high-severity items outside the
  top priorities" counted real data-loss defects that a change rightly rated high. Before dropping
  a variant for noise, ask what that noise costs the reader.
- **Count by hand, blind, when one arm cannot be scored by machine.** Count every arm with one
  written rule, on copies under random labels, keep the mapping apart, and verify the decisive
  quotes yourself.
- **Matchers need adversarial review too.** A term such as `500` also matches inside `5000`; a
  missed item can be a correct answer under a label the matcher did not list.
- **Record what you did not plan for.** A real problem that a run finds and no criterion seeded
  joins the test material, dated.
- **Check what actually ran:** the model the run's record reports, the version of the text, and
  whether the run overlapped another on the same resources.
