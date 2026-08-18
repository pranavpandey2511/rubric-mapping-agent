# Part 2 Prompt Evolution

This document records the Part 2 prompt changes in chronological order. Part 2
is an internal retrieval stage rather than an assignment-evaluated artifact, so
its results are structural diagnostics and downstream Part 3 evidence—not Part
2 precision, recall, or F1.

Part 2 implements the project-defined handoff:

> create_intermediate_sections(input.xlsx, complete.xlsx, instructions.md,
> sections.json, summary.md) -> subsections.json + subsection_index.json

rubric.json has never been included in the Part 2 generation context.

## Revision summary

| Revision | Main change | Measured outcome | Decision |
|---|---|---|---|
| Initial output handoff | `subsections.json` plus a coordinate-free `summary.md` | Implemented in the initial pipeline | Summary later replaced by a structured index |
| Baseline | Open-ended semantic axes and free-form tags | Keysight: 451 subsections, 27 role names, 80 separator subsections | Too noisy for retrieval |
| Retrieval-oriented v2 | Formula/calculation families, controlled roles, no separator-only units | Keysight: 177 subsections, 11 used roles, zero separators, same diff coverage | Kept |
| Context ablation support | Allow Part 3 to run with Part 1+2, Part 1 only, or neither | Implemented, not run as a clean recorded study | Still needed to prove Part 2's value |

## 0. Initial scaffold

### Why it existed

The assignment describes an intermediate Part 2 concept but does not require a
public Part 2 function or provide a gold subsection schema. The initial project
created `subsections.json` plus a coordinate-free `summary.md` to preserve
rubric-independent semantics for Part 3 while keeping the stage independently
runnable.

### Exact starting policy

The initial prompt asked the model to:

> Represent multiple semantic axes

It listed historical/projected, input/output, linked/calculated,
controls/schedules, labels/values, scenarios, calculations, checks, metadata,
and notes.

The role policy was deliberately open:

> These are tags, not a universal fixed taxonomy. Infer them from period labels,
> cell types, formula dependencies, formats, nearby text, and task instructions.

It preferred:

> a stable primary subsection membership for each relevant cell, then attach
> multiple semantic tags.

Blank handling was already different from Part 1:

> Do not force blank cells into a subsection merely to complete a rectangle.

This was intentional because a Part 2 retrieval unit does not need to reproduce
the full visual footprint of its parent Part 1 panel.

## 1. Shared file-handoff prompt revision

Before the first measured end-to-end Part 2 study, the common stage prompt
changed from returning the complete artifact in the model's structured response
to writing it to a declared hosted path:

> CONTAINER_OUTPUT: /mnt/data/subsections.json

> Write compact UTF-8 JSON there ... Do not print or repeat the artifact and do
> not create any other file. Return only the structured receipt containing the
> artifact path.

### Why this changed

Part 1 had already demonstrated that thousands of explicit cell addresses could
be created correctly inside Code Interpreter but fail during the final
structured-response handoff. The same failure mode applied to subsections.json,
so the shared prompt transport was changed before relying on Part 2 output.

This changed how the prompt returns data, not how subsections are selected.

## 2. Retrieval-oriented v2

### Why this changed

The first complete Keysight pipeline exposed two separate findings:

1. Part 2 coverage was not the cause of Part 3's low recall. Every Part 3
   false-negative gold cell was already present in a Part 1 section and Part 2
   subsection.
2. The Part 2 representation itself was noisy:
   - 451 subsections
   - 27 different role names
   - 80 separator subsections
   - 729 cells assigned to separator-only subsections

Part 3 before its own prompt redesign scored 99.36% precision, 58.78% recall,
and 70.20% F1 on Keysight. Of 1,068 false-negative mappings, 1,008 came from
entire omitted item, worksheet, or row families. Upstream retrieval coverage
already existed; the mapper was selecting too little from it.

The Part 2 goal was therefore narrowed from an exhaustive workbook taxonomy to
a compact retrieval index.

### Exact objective change

The heading changed from:

> Represent multiple semantic axes

to:

> Build retrieval-oriented subsections

The new definition is:

> A subsection is a coherent financial concept or calculation family that
> helps a later mapper retrieve all evidence for one possible grading
> requirement. It is not merely a visual row, formatting block, or exhaustive
> taxonomy.

### Exact grouping changes

The prompt now says:

> keep copy-across or copy-down formula families together

> keep a small set of rows together when they jointly implement one named
> calculation, schedule, control, check, or output

> separate historical and projected cells when their source or calculation
> behavior differs

> distinguish assumptions, linked values, local calculations, controls, checks,
> and outputs when they are independently meaningful evidence

> keep a local identifying label with its value or formula family, while shared
> period headers may remain separate context

> allow non-contiguous membership when the cells implement the same financial
> object

### Exact membership changes

The baseline allowed broad semantic tagging. The new prompt favors one stable
primary membership and permits secondary membership only when a cell genuinely
bridges two financial objects.

It explicitly removes whitespace taxonomy:

> Do not create a subsection whose only purpose is whitespace or visual
> separation.

> Omit non-applicable blanks and spacer cells. Retain a blank cell only when it
> is an intentional input, template, or future-period modeling cell.

### Exact role-vocabulary change

The open-ended instruction:

> not a universal fixed taxonomy

was removed. The prompt now allows only:

> historical, projected, input, assumption, linked, calculation, control,
> output, check, header, template, scenario, sensitivity

It also says:

> Do not invent synonyms or workbook-specific role names.

### Exact final-audit change

Before writing subsections.json, the agent must now confirm:

- every relevant input-to-complete diff cell is reachable;
- repeated formula families were not accidentally split across periods;
- no subsection contains only blank separators;
- adjacent tiny subsections are merged when they implement the same concept;
- the Part 1 footprint was not copied mechanically into Part 2.

### Results on the first controlled Keysight rerun

| Diagnostic | Before | After |
|---|---:|---:|
| Subsections | 451 | 177 |
| Role names used | 27 | 11 |
| Separator subsections | 80 | 0 |
| Separator cells | 729 | 0 |
| Eligible diff coverage | 1,262 / 1,263 | 1,262 / 1,263 |

The 191 secondary memberships in the new output were column-C row labels shared
between historical and projected families, not duplicated numerical evidence.

### Results across all three workbooks

| Example | Subsections | Eligible diff coverage | Separator subsections |
|---|---:|---:|---:|
| Keysight | 177 | 1,262 / 1,263 (99.92%) | 0 |
| Textron-1 | 96 | 1,337 / 1,337 (100.00%) | 0 |
| TopBuild | 177 | 1,051 / 1,051 (100.00%) | 0 |
| **Combined** | **450** | **3,650 / 3,651 (99.97%)** | **0** |

Twelve of the allowed roles appeared across the three-workbook experiment.

### Decision

Keep this prompt. It reduced representation noise without losing meaningful diff
coverage.

The result does not establish Part 2 semantic accuracy: there is no gold
subsections.json, and high diff coverage alone does not prove that the groups
are useful.

## 3. Part 2 value ablation support

### Why this changed

The audit found that Part 2's handoff is still lossy. It preserves coordinates,
parent section IDs, and coarse roles, but not the richer concepts the model
likely used internally, such as formula-family identity, label lineage,
period interpretation, dependencies, target-versus-context status, or
confidence.

Before expanding the schema, the project needs to prove that Part 2 improves
Part 3 at all.

### Exact configuration change

The complete workflow now supports:

> RUBRIC_MAP_PART3_CONTEXT=part1_part2

Part 3 receives sections.json and subsections.json. As of the 2026-08-18
handoff revision, Part 2 also receives Part 1 `summary.md` as semantic
orientation. The workbooks and `sections.json` remain authoritative for exact
coordinates; the summary is not coordinate evidence. This addition has not yet
been validated through a fresh downstream Part 3 comparison.

> RUBRIC_MAP_PART3_CONTEXT=part1

Part 3 receives sections.json only and Part 2 is skipped.

> RUBRIC_MAP_PART3_CONTEXT=none

Part 3 receives neither upstream artifact and Part 2 is skipped.

### Measurement status

The switches, named ablation variants, and local tests were added. The recorded
live work then prioritized Part 3 evidence-policy experiments with frozen
Part 1 and Part 2 artifacts. No saved, clean three-workbook comparison of
part1_part2 versus part1 versus none was completed.

Therefore the current evidence supports:

- Part 2 is structurally compact and has nearly complete diff coverage.
- Part 3 failures were not caused by Part 2 omitting the gold cells.

It does not yet support:

- Part 2 improves Part 3 F1.
- Part 2 reduces model cost or latency.
- The current five-field subsection schema is better than direct workbook
  retrieval.

## 4. Replace the initial prose-summary handoff

### Initial output contract

The initial pipeline returned strict `subsections` plus internal
`subsection_summaries`. The host preserves the existing five-field
`subsections.json` contract and renders a separate `summary.md` containing each
subsection ID, parent, title, technical detail, plain-language explanation,
roles, and worksheet. The summary deliberately contains no cell coordinates;
`subsections.json` is the sole coordinate-bearing Part 2 artifact.

Part 2 accepted Part 1 JSON, Part 1 summary, or both according to the two global
handoff flags; at least one channel was required. Both Part 2 output files were
generated regardless of those flags. In a summary-only handoff, the prose gave
semantic orientation while the model re-identified geometry from the
workbooks; the host still validated its output against the retained
authoritative Part 1 JSON.

### Replacement decision

The Part 2 prose summary did not work well enough as downstream retrieval
context. Following Codex's suggestion, it was replaced with the structured
`subsection_index.json`, which records semantic families, metadata, and direct
typed relationships. Current Part 2 writes `subsections.json` and
`subsection_index.json` directly and does not produce a Markdown summary.

### Measurement status

Implemented as a contract and orchestration change. It has no standalone gold
artifact and has not yet been shown to improve Part 3 quality, latency, or cost.

## 5. Conditional visual semantic-grouping evidence

### Why this changed

Part 2 can benefit from visual layout when semantic grouping remains ambiguous,
but its subsections must not collapse into formatting blocks. The optional tool
therefore needed a Part 2-specific decision boundary rather than only a generic
system-prompt announcement.

### Exact change

Part 2 now has a complete
[`part-2-workflow-visual.md`](../../skills/xlsx-rubric-mapping/references/part-2/part-2-workflow-visual.md)
variant. It permits bounded parent-region inspection after structural analysis
to interpret multi-level headers, explicit period or scenario bands, merged
labels, control/check placement, and separated groups that may implement one
named object. Visual evidence cannot expand the Part 1 parent, establish cell
membership, or turn formatting and proximity into a semantic or formula
relationship. The runtime exposes this variant under the canonical
`part-2-workflow.md` name only when the visual tool is attached.

### Measurement status

Implemented and covered by prompt-routing tests. There is still no gold Part 2
subsection artifact, and the change has not been shown to improve downstream
Part 3 quality, latency, or cost.

## Current state

The effective Part 2 prompt is:

1. Either normal [part-2-workflow.md](../../skills/xlsx-rubric-mapping/references/part-2/part-2-workflow.md)
   or complete visual
   [part-2-workflow-visual.md](../../skills/xlsx-rubric-mapping/references/part-2/part-2-workflow-visual.md),
   exposed under the canonical `part-2-workflow.md` name
2. [output-format.md](../../skills/xlsx-rubric-mapping/references/part-2/output-format.md)
3. The shared workbook-inspection rules in the skill entrypoint
4. The shared hosted output-path instruction

The visual variant changes only the available inspection workflow; it does not
change Part 2's semantic or output contracts. Its quality effect remains
unmeasured.

The current outputs are `subsections.json` plus `subsection_index.json`; there is
no Part 2 `summary.md`.

## Evidence used

- Codex task "Run part one with LangSmith" (2026-08-17)
- Codex task "Review three-stage extraction" (2026-08-17)
- Saved subsections under artifacts/predictions
- Local ignored report retained at
  `artifacts/reports/prompt-v2-all-three-2026-08-17.md`
- Current prompt files and the committed baseline in Git
