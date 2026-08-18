# Part 1 Prompt Evolution

This document records the Part 1 prompt changes in chronological order. It
separates prompt wording, orchestration changes that alter the effective prompt
context, measured results, and changes that are implemented but not yet
measured.

Part 1 implements:

> create_overall_section(input.xlsx, complete.xlsx, instructions.md) -> sections.json

The rubric and gold section files were never added to the generation context.

## Revision summary

| Revision | Main change | Measured outcome | Decision |
|---|---|---|---|
| Baseline | General semantic block detection | Keysight F1 74.25% | Recall was too low |
| v2 | Fill all cells inside a chosen block; prompt-level sheet sequencing | Keysight diagnostic F1 76.03% | Recall fixed, precision collapsed |
| v3 | Boundary first, then blank-cell inclusion; JSON file handoff | Three-task macro F1 86.73% | Stable conservative baseline |
| v4 | Broader hierarchy, sidecar, and helper rules | Three-task macro F1 59.39% | Rejected and rolled back |
| v5 | Fresh invocation per sheet plus local edge audits | Three-task macro F1 89.83% | Best measured Part 1 revision in the focused study |
| Policy split | Preserve v5 as current; add high-level policy | Not independently rerun | High-level was temporarily configured but unverified |
| Tightened current + summaries | Restore v5/current; add anti-overmerge audit and section descriptions | Revised prompt not yet rerun | Current is again the default; live validation remains pending |
| Hierarchy/responsibility pass | Merge leaf panels by responsibility and treat headers as contextual | Macro P/R/F1 94.72% / 85.87% / 88.99% | Rejected; recall rose, but precision and F1 fell versus the best run |
| Context ownership + band union | Three-way header ownership and non-rectangular band geometry | Macro P/R/F1 100.00% / 76.86% / 86.30% | Rejected and rolled back; precision recovered by losing too much recall |

## 0. Initial scaffold

### Why it existed

The first prompt had to solve the assignment without seeing rubric.json. It
combined deterministic workbook inspection with model judgment about financial
meaning and used the evaluator's pairwise section metric to explain the
precision/recall trade-off.

### Exact starting policy

The central objective was:

> Group cells into high-level regions whose contents form a cohesive financial
> object: a schedule, statement, assumptions area, controls block, valuation
> output, or comparable semantic unit.

The boundary guidance included:

> Include meaningful blank cells inside the block's layout or formatting
> footprint.

> Separate neighboring schedules when multiple signals show a change of
> purpose.

> Generate candidate geometry deterministically; let the model select or revise
> candidates using financial semantics.

### What the first measured run showed

Keysight produced 24 sections and 3,188 unique cells:

| Precision | Recall | F1 |
|---:|---:|---:|
| 95.94% | 60.56% | 74.25% |

The high precision and low recall indicated under-grouping and omitted
relationships. Because the evaluator scores every within-section cell pair,
splitting one correct large section into smaller sections can cut recall roughly
in half even when most individual cells are present.

### Decision

Keep the semantic model-based boundary decision, but make blank-cell membership
and weak-boundary splitting much more explicit.

## 1. v2: complete blank-cell membership and prompt-level sheet sequencing

### Why this changed

The first output omitted cells that were blank in both workbooks even when they
were inside a visibly bounded panel. The concrete Keysight example was the
Financial Statement Modeling header block: the expected section covered C2:M9,
including all blank coordinates inside that footprint.

There was also concern that one model context containing every sheet caused
cross-sheet distraction.

### Exact change

The prompt changed from the softer rule:

> Include meaningful blank cells inside the block's layout or formatting
> footprint.

to the stronger rule:

> Once one rectangular block has been selected as a section, include every
> coordinate from its top through bottom row and left through right column.
> Include cells that are empty, unstyled, or empty in both workbook versions.

It also added:

> Treat blank rows, blank columns, and large empty areas inside an enclosing
> border or continuing layout as section members, not automatic separators.

> Do not split solely because of one blank or sparse row, a subtotal, a
> historical-to-projected transition, a value-to-formula transition, one
> formula-family change, or one style change.

The prompt instructed the existing single invocation to work through worksheets
sequentially:

> Process worksheets in workbook order. For each worksheet, inspect the matching
> sheet in input.xlsx and complete.xlsx as one isolated sheet pair, finish its
> Part 1 boundary decisions and exact cell membership, and only then move to the
> next sheet.

A four-edge audit was also added: inspect immediately inside and outside every
proposed top, bottom, left, and right edge before finalizing the section.

### Result

The recovered Keysight prediction was:

| Precision | Recall | F1 |
|---:|---:|---:|
| 62.00% | 98.27% | 76.03% |

The C2:M9 example became exact, but several financial schedules were expanded
into unsupported large rectangles. False negatives fell from 190,053 to 8,347,
while false positives rose from 12,356 to 290,194.

The official handoff also failed: the agent created the large artifact in Code
Interpreter but returned an empty sections list in the structured response. The
immutable pre-gold artifact was recovered only for diagnosis.

### Decision

The blank-cell rule was correct, but it had to apply only after the outer
footprint was established. Rectangular completion could not be used as evidence
for choosing or widening the footprint.

## 2. v3: choose the boundary first, then fill it

### Why this changed

v2 fixed recall by over-expanding. The next prompt needed to distinguish two
separate decisions:

1. Which cells define the panel's true outer footprint?
2. Once that footprint is confirmed, which interior blank cells belong?

The output transport also needed to handle thousands of explicit cell
addresses reliably.

### Exact stage-prompt change

The boundary policy was tightened to:

> Use each panel's own title or header span, enclosing borders, fills, merged
> cells, row labels, and financial purpose to choose the smallest footprint
> supported on all sides.

> Include titles, units, headers, labels, values, formulas, totals, controls,
> and every blank cell inside that confirmed footprint. A blank cell inherits
> membership from the surrounding panel; blankness is never evidence for
> expanding the panel.

> Do not extend a section to the worksheet's populated or styled bounds, to
> hidden helper formulas, or merely to complete a larger rectangle.

The prompt explicitly removed Python from semantic boundary selection:

> The model decides section membership. Use Python only to inspect workbook
> evidence and enumerate the chosen exact addresses; do not ask Python to
> propose candidate rectangles or decide boundaries.

It also restricted the response:

> Return no ranges, boundary descriptions, candidate regions, drawings, or
> diagnostics.

### Exact shared output-prompt change

All stages changed from returning the full artifact through the structured
response:

> Return the requested JSON object inside the artifact field.

to writing it to one declared hosted path:

> Write the exact requested JSON artifact only to that path. Do not print or
> repeat the artifact ... Return only the output path in the artifact_path
> field.

For Part 1, the effective dynamic prompt declares:

> CONTAINER_OUTPUT: /mnt/data/sections.json

This was an operational prompt change, not a semantic sectioning change. It
fixed the v2 large-output handoff failure.

### Results

One Keysight run improved to:

| Precision | Recall | F1 |
|---:|---:|---:|
| 99.9903% | 95.8447% | 97.8736% |

The broader three-example rerun showed meaningful model variance:

| Example | Precision | Recall | F1 |
|---|---:|---:|---:|
| Keysight | 100.00% | 84.58% | 91.65% |
| Textron-1 | 100.00% | 59.75% | 74.81% |
| TopBuild | 96.37% | 91.26% | 93.75% |
| **Task macro** | **98.79%** | **78.53%** | **86.73%** |

v3 eliminated the catastrophic footprint expansion but still over-split large
objects. Textron also omitted its small Dropdowns worksheet.

### Decision

Use v3 as the conservative baseline. Improve hierarchy and functional helper
coverage narrowly rather than loosening all boundaries.

## 3. v4: broad hierarchy, sidecar, and helper recognition

### Why this changed

v3's dominant problem was fragmentation:

- Keysight split large Revenue Build and DCF objects.
- Textron split large Operating_Model panels.
- Textron omitted the functional Dropdowns worksheet.
- Some attached period, variance, CAGR, scenario, or check columns were at risk
  of being separated from their parent panel.

### Exact change

The prompt added:

> Choose the smallest complete top-level panel, not the smallest populated
> cluster, using title hierarchy, enclosure, headers, financial role, and
> formulas.

> A parent title or frame owns its child tables; internal labels, gaps, and
> related driver families do not create sections by themselves.

> Split only when multiple signals agree: a same-level title, enclosure reset,
> new local period axis, or clear role transition.

> Include an attached period header or sidecar such as CAGR, variance, check,
> or scenario when alignment, shared enclosure, or formulas show ownership.

> Treat a compact lookup, dropdown, control, or helper table as a section when
> formulas, defined names, or data validation use it, even if it is small or
> unstyled.

### Result

| Example | Precision | Recall | F1 | Previous v3 F1 |
|---|---:|---:|---:|---:|
| Keysight | 33.27% | 99.10% | 49.81% | 91.65% |
| Textron-1 | 86.05% | 59.89% | 70.63% | 74.81% |
| TopBuild | 40.82% | 98.62% | 57.74% | 93.75% |
| **Task macro** | **53.38%** | **85.87%** | **59.39%** | **86.73%** |

The functional Dropdowns rule worked, but the hierarchy and sidecar rules were
too permissive:

- Keysight merged independent Financial Statement panels into C105:M237.
- TopBuild expanded panels into unrelated helper/side columns.
- Textron's main fragmentation problem remained.

### Decision

Reject v4. Restore v3's conservative boundary rule, keep only narrowly defined
helper detection, and fix the procedural problem by giving each worksheet a
fresh context.

## 4. v5: actual per-sheet isolation and local boundary procedure

### Why this changed

Prompt-only "one sheet at a time" was not true isolation. LangSmith traces showed
the agent still used a global workbook dump and manually constructed rectangles.
All sheets and prior observations shared one conversation and Code Interpreter
container.

### Exact orchestration prompt change

Part 1 now runs once per worksheet. Each dynamic prompt includes:

> TARGET_SHEET: "the exact worksheet name"

> This invocation covers only TARGET_SHEET. Inspect cell-level contents only
> for that exact worksheet in input.xlsx and complete.xlsx, and return sections
> only for that worksheet.

Each call gets a fresh agent, conversation, and hosted container. The host
combines the per-sheet artifacts and renumbers arbitrary section IDs; it does
not infer, fill, merge, or split geometry.

### Exact stage-prompt change

The v4 hierarchy language was replaced with a local inspection sequence:

> Inventory that sheet's local titles, header and period axes, enclosures,
> merged cells, populated cells, styled blanks, formula patterns, and controls.

> Identify tentative panels without using a raw whole-workbook dump or task
> instructions as coordinate or extent evidence.

The boundary rule became:

> Choose the smallest complete panel supported by its local title or header,
> enclosure, financial role, and formulas. Keep uncertain neighboring panels
> separate.

> Keep adjacent blocks together only when one uninterrupted local period or
> header axis governs the combined area and no same-level title, enclosure,
> role, or axis reset intervenes.

The helper rule was narrowed:

> Include only that helper table's tight occupied footprint; do not pad it
> through surrounding blanks.

The prompt also required all four outer edges to stop before:

> a new title, axis, enclosure, helper area, or blank/default exterior.

### Result

| Example | v3 F1 | v4 F1 | v5 Precision | v5 Recall | v5 F1 |
|---|---:|---:|---:|---:|---:|
| Keysight | 91.65% | 49.81% | 100.00% | 92.48% | 96.09% |
| Textron-1 | 74.81% | 70.63% | 98.97% | 60.29% | 74.93% |
| TopBuild | 93.75% | 57.74% | 100.00% | 96.95% | 98.45% |
| **Task macro** | **86.73%** | **59.39%** | **99.66%** | **83.24%** | **89.83%** |

Textron Dropdowns became exact. The remaining bottleneck was hierarchy selection
inside Textron Operating_Model: the model still found nearly all cells but
split one large gold object into many local panels.

A later full-pipeline run of the same general v5/current behavior produced a
Part 1 task-macro score of 100.00% precision, 84.61% recall, and 90.60% F1.
That later run is the frozen upstream used by the Part 3 ablations.

### Decision

Keep v5 as the reproducible "current local panels" policy.

## 5. Policy split: current local panels versus high-level sections

### Why this changed

The three-stage audit showed that Part 1 was often selecting Part 2-level
granularity. Textron's unique-cell coverage was high, but splitting one gold
Operating_Model section into several predicted sections destroyed cross-fragment
pairs. The next hypothesis was to select a higher hierarchy cut without
reintroducing v4's blanket merging.

### Exact refactor

The common Part 1 prompt no longer hardcodes merge-versus-split behavior. It now
says:

> The caller selects exactly one part-1-policy-*.md reference. Treat that file
> as authoritative for the section granularity and merge-versus-split decision.
> Do not blend it with another Part 1 policy.

The previous v5 rule was preserved at the time in
`part-1-policy-current.md`:

> Choose the smallest complete panel supported by its local title or header,
> enclosure, financial role, and formulas.

The experimental `part-1-policy-high_level.md` added:

> Choose high-level financial modules, not the smallest local panels.

> A subordinate title, blank separator, historical/projected transition, or
> repeated local axis does not by itself create a Part 1 boundary.

> Split peer high-level objects when more than one independent signal changes.

> Never emit a heading-only row as its own section.

The high-level policy is selected by default with:

> RUBRIC_MAP_PART1_POLICY=high_level

The earlier behavior remains available with:

> RUBRIC_MAP_PART1_POLICY=current

### Measurement status

This policy split and default were implemented and covered by local tests, but
the recorded live ablation sequence then prioritized Part 3. There is no clean
three-workbook Part 1 evaluation in the saved history that changes only
RUBRIC_MAP_PART1_POLICY from current to high_level.

Therefore:

- 89.83% is the focused v5 Part 1 macro F1.
- 90.60% is the later frozen current-upstream Part 1 macro F1.
- Neither number validates the new high-level default.

## 6. Restore the best measured base, tighten merges, and add summaries

### Why this changed

A clean live Keysight run of the `high_level` policy on 2026-08-18 produced 17
predicted sections against 26 gold sections. The grouped-pair result was 31.90%
precision, 100.00% recall, and 48.37% F1. All gold relationships were covered,
but 1,028,962 false-positive pairs showed that the policy merged independent
panels into overly broad modules.

This is direct evidence against keeping `high_level` as the default. The best
measured base remains v5/current: 89.83% macro F1 in the focused study and
90.60% in the later frozen-upstream run.

### Exact changes

The default returned to:

> RUBRIC_MAP_PART1_POLICY=current

The current policy retains the v5 local-panel rule and now makes the
anti-overmerge decision explicit:

> A new same-level title, a reset local period axis, a new enclosure, or a clear
> change in financial purpose is enough to keep two neighboring panels
> separate.

> Never widen a section to the worksheet's used/styled bounds or merge panels
> merely to reduce the predicted section count, improve recall, or avoid the
> grouped-pair penalty for fragmentation.

Part 1 also creates one title and one-to-three-sentence description after each
section's geometry is final. Per-sheet descriptions use local section IDs; the
host renumbers them with the combined `sections.json` IDs and renders
`summary.md`. The strict evaluator artifact remains unchanged. Part 2 receives
both artifacts, using the summary as semantic orientation rather than as
coordinate evidence.

### Measurement status

The 48.37% result measures the rejected `high_level` policy. The restored v5
base is measured historically, but the newly tightened wording and summary
handoff have not yet been rerun. They are implemented candidates, not a new
quality claim.

## 7. Structured coordinate-free semantic sidecar

### Exact changes

Part 1 still emits evaluator-compatible `sections.json`, but each internal
summary record now contains exactly `section_id`, `title`, `detail`, and
`plain_language`. The host renders those records with worksheet names into
`summary.md`, which deliberately contains no cell coordinates. `sections.json`
is the only coordinate-bearing Part 1 artifact. Both files are generated on
every Part 1 run.

The default-on `RUBRIC_MAP_HANDOFF_JSON` and
`RUBRIC_MAP_HANDOFF_SUMMARY` flags independently control which validated
artifacts the next agent sees.

### Measurement status

The summary contract was exercised in the August 18 hierarchy and precision
repair runs, so artifact compatibility is live-validated. Its independent
effect on Part 1 accuracy has not been isolated from the semantic prompt changes
in those runs.

## 8. Hierarchy and responsibility experiment

### Hypothesis

The v5/current prompt remained conservative on Textron's large Operating_Model
object. The experiment added leaf-panel discovery followed by a separate
hierarchy pass, classified candidates by responsibility, and permitted merging
when neighboring candidates appeared to form one higher-level object. It also
biased worksheet titles, selectors, units, and shared axes toward the first
module they governed.

### Measured result

| Example | Precision | Recall | F1 |
|---|---:|---:|---:|
| Keysight | 91.96% | 96.91% | 94.37% |
| Textron-1 | 97.73% | 62.76% | 76.44% |
| TopBuild | 94.49% | 97.93% | 96.18% |
| **Task macro** | **94.72%** | **85.87%** | **88.99%** |

Against the 90.60% frozen-upstream result, macro recall improved by 1.26
percentage points, but precision fell by 5.27 points and F1 fell by 1.61 points.
The dominant precision error was attaching independent metadata or umbrella
headers to the first child module. Textron's large Operating_Model object still
remained fragmented.

### Decision

Reject the broad hierarchy pass as the default. Do not trade the measured v5
precision boundary for generic responsibility-based merging.

## 9. Context ownership and union-of-bands precision repair

### Hypothesis

Starting from the hierarchy experiment, the prompt added a three-way decision
for leading metadata and contextual headers and allowed one semantic section to
be an exact union of separately bounded rectangular bands. The goal was to
remove the observed false-positive merges without losing the hierarchy run's
recall gain.

### Measured result

| Example | Precision | Recall | F1 | Run ID |
|---|---:|---:|---:|---|
| Keysight | 100.00% | 80.19% | 89.00% | `20260818T122112.721395Z` |
| Textron-1 | 100.00% | 59.76% | 74.81% | `20260818T122132.863162Z` |
| TopBuild | 100.00% | 90.64% | 95.09% | `20260818T122129.842863Z` |
| **Task macro** | **100.00%** | **76.86%** | **86.30%** | — |

The model generalized band geometry into sparse footprints. Ordinary rectangular
panels omitted internal blank cells, while Textron emitted the schedule body but
missed its narrower period-header band. The contextual rule also fragmented
metadata areas rather than consistently emitting one complete panel.

### Decision

Reject and roll back both semantic changes. Restore the exact v5/current
boundary rules. Retain only non-boundary improvements: the explanation of
`input.xlsx` versus `complete.xlsx`, the strict evaluator-compatible artifact,
and coordinate-free section summaries required by the current runtime.

## 10. Conditional visual boundary evidence

### Why this changed

The optional LibreOffice visual backend made a read-only
`inspect_workbook_view` tool available to the agent, but Part 1 did not state
where visual evidence belongs in its boundary workflow. A generic capability
announcement was not enough to distinguish useful boundary inspection from
routine or authoritative screenshot use.

### Exact change

Part 1 now has a complete
[`part-1-workflow-visual.md`](../../skills/xlsx-rubric-mapping/references/part-1/part-1-workflow-visual.md)
variant of the normal workflow. It adds bounded viewport inspection after
structural analysis for unresolved titles, merged headers, enclosures,
whitespace, repeated axes, controls, and all four proposed panel edges. It may
compare matching input and complete regions. Screenshots can confirm or
challenge a structurally supported boundary but cannot establish coordinates,
override workbook evidence, or justify visually enclosed cells by themselves.
The runtime exposes this variant under the canonical `part-1-workflow.md` name
only when the tool is attached; otherwise it exposes the normal source.

### Measurement status

Implemented and covered by prompt-routing tests. The headless renderer has a
passing local integration smoke test, but this prompt change has not yet been
measured on the three-example Part 1 benchmark. It must not be attributed an
accuracy effect until a controlled run records actual tool calls and scores.

## Current state

The effective Part 1 prompt is composed from:

1. Either normal [part-1-workflow.md](../../skills/xlsx-rubric-mapping/references/part-1/part-1-workflow.md)
   or complete visual
   [part-1-workflow-visual.md](../../skills/xlsx-rubric-mapping/references/part-1/part-1-workflow-visual.md),
   selected from actual tool availability and exposed under the canonical
   `part-1-workflow.md` name
2. [output-format.md](../../skills/xlsx-rubric-mapping/references/part-1/output-format.md)
3. The dynamic TARGET_SHEET and CONTAINER_OUTPUT instructions

The runtime policy selector was retired when the references were consolidated.
The workflow now restores the measured v5/current semantic boundary policy:
smallest complete local panels, conservative uncertain boundaries, strict
shared-axis merging, full rectangular interiors, tight helper footprints, and
four-edge audits. They retain the later explanation of the two workbook states
and the coordinate-free section summaries required by the current runtime.

The 90.60% result remains historical evidence from the saved August 17 run, not
a guarantee for a stochastic rerun. A clean confirmation must keep the same
model, 4 GB container tier, sheet scope, workbook inputs, and evaluator, and
should record the prompt and prediction hashes before scoring.

## Evidence used

- Codex task "Run part one with LangSmith" (2026-08-17)
- Codex task "Review three-stage extraction" (2026-08-17)
- Saved predictions under artifacts/predictions
- Local ignored report retained at
  `artifacts/reports/prompt-v2-all-three-2026-08-17.md`
- Current prompt files and the committed baseline in Git
