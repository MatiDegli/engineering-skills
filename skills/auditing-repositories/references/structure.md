# Organization and cleanup

Organize by responsibility and respect existing boundaries. File count is a prompt to review
cohesion; it does not determine the structure by itself.

## Review

| Situation | Treatment |
| --- | --- |
| More than 20 source files directly in one directory | Warning to review cohesion; no numeric block |
| New file at the root outside agreed locations | Block integration until it is moved or an exception is approved |
| Dependency that violates an agreed boundary | Block until it is corrected or the decision is formally reviewed |
| Temporary script with no purpose, owner, or removal condition | Resolve before closing the milestone |

The threshold of 20 is an initial value and may be reviewed. Count maintained source files,
including tests and tools, without counting subdirectories. Exclude generated files, files that
hold only data, migrations, fixtures, and resources by path and purpose; this exclusion affects
only the count, not other controls.

When the threshold is exceeded, review distinct responsibilities, coupling, and difficulty
finding changes. Record whether to keep or reorganize, with a reason. Avoid artificial splits,
empty directories, or giant files created to evade the warning.

## Locations and boundaries

Agree in the README on locations for code, tests, docs, tools, and generated files;
keep existing names that work. Reserve the root for documentation entry points, manifests,
lockfiles, and configuration that needs to be there. An exception identifies the path and reason.

Define allowed dependencies between real modules and express them as import contracts
when useful. A reorganization preserves behavior, commands, and links; check for cycles.

## Temporary files and enforcement

Each retained temporary file needs a purpose, owner, and verifiable removal condition in its
header or a tracking record. At milestone close: remove it, turn it into a maintained tool,
or justify an extension. Check references and preserve others' work before deleting anything.

These are review rules until the project automates them. If it adopts a checker,
file counts issue warnings; disallowed locations and dependencies block with reviewed exceptions.
Test violations, allowed cases, and exclusions.
