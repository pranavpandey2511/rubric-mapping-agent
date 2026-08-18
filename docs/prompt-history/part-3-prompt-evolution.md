# Part 3 Prompt Evolution

This document records the Part 3 prompt changes in chronological order. It
distinguishes actual model-run policies from post-run diagnostic combinations.

Part 3 implements:

> create_items_to_cells_mapping(input.xlsx, complete.xlsx, instructions.md,
> rubric.json) -> items_to_cells.json

Gold items_to_cells.json files and evaluator outputs were never part of the
generation context. Every measured prompt was constrained to input-to-complete
diff cells by the host validator.

## Revision summary

| Revision | Main change | Task-macro precision / recall / F1 | Decision |
|---|---|---|---|
| Initial policy | Small evidence-backed mappings | Not run on all three in this form | Too precision-biased on Keysight |
| Complete evidence | Atomic requirements plus named inputs, intermediates, and outputs | 70.20 / 96.43 / 76.49% | Recall fixed, dependency false positives exploded |
| Minimal evidence | Target/result/destination cells by default | 99.89 / 75.34 / 82.61% | Better overall, too aggressive for numerical-credit items |
| Scoring-aware v1 | Broad for numerical credit, minimal for method-only | 99.83 / 78.69 / 85.19% | Best at the time, Keysight recall still low |
| Scoring-aware v2 | Numerical-family completeness is a hard override | 99.15 / 85.33 / 89.55% | Current default and strongest tested single prompt |

## 0. Initial precision-oriented policy

### Why it existed

The starting prompt emphasized avoiding oversized mappings because Part 3 is
scored item by item. It built a deterministic eligible diff, retrieved
candidates using workbook semantics, and asked the model to prefer compact
evidence.

### Exact starting policy

The original prompt said:

> whether the cell is the evidence a judge should inspect, not merely a remote
> supporting precedent

and:

> Prefer a small evidence-backed set over arbitrary section-wide coverage

It also said:

> Do not map an entire section when the item concerns one row, one period band,
> or one assumption family.

### What the first complete Keysight run showed

| Precision | Recall | F1 |
|---:|---:|---:|
| 99.36% | 58.78% | 70.20% |

Cell totals were 1,321 true positives, 16 false positives, and 1,068 false
negatives.

The error was systematic:

- 1,008 of the 1,068 false negatives came from entire omitted item, worksheet,
  or row families.
- Every false-negative gold cell was already inside Part 1 and Part 2.
- The mapper often returned only a final total or output row even when the
  rubric explicitly named component calculations.

Examples included selecting Total Assets but omitting its named component rows,
or selecting UFCF while omitting the explicitly named NOPAT, D&A, stock
compensation, working-capital, and capex families.

### Decision

Replace the small-set objective with a rubric-clause coverage objective. Keep
the deterministic diff boundary and the prohibition on arbitrary section-wide
mapping.

## Shared operational prompt revision before the Part 3 studies

The common agent and skill prompts changed how every stage transports its final
artifact. Part 3 changed from returning the full mapping inside a structured
response to writing it in hosted Code Interpreter:

> CONTAINER_OUTPUT: /mnt/data/items_to_cells.json

> All task files are read-only. Your sole permitted write is CONTAINER_OUTPUT.

> Do not print or repeat the artifact and do not create any other file. Return
> only the structured receipt containing the artifact path.

The shared division-of-labor instruction was also clarified. Deterministic code
could inspect exact evidence and, in Part 3, form item-to-cell candidates, while
the model remained responsible for semantic ranking and selection.

### Why this changed

Large explicit-cell artifacts had already failed when copied from Code
Interpreter into a final structured response during Part 1. File transport
prevented the same failure for items_to_cells.json and kept the final model
response small. The read-only and single-output rules also made it explicit
that workbook inspection must not modify the supplied files or create
evaluator-visible diagnostics.

This was an operational prompt change. It did not change which cells Part 3
considered correct.

## 1. Complete-evidence prompt

### Why this changed

The previous prompt was interpreting "evidence" as only the final result. The
new hypothesis was that every explicitly named atomic rubric requirement should
have mapped evidence, including named inputs, calculations, and outputs.

### Exact objective change

The heading changed from:

> Retrieve candidates before final reasoning

to:

> Map the complete rubric-bounded evidence set

The prompt removed:

> Prefer a small evidence-backed set

and added:

> Split the condition into atomic requirements. Include every named financial
> object, input, assumption, link, calculation, output, period, scenario, and
> method.

> Part 1 and Part 2 are retrieval hints, not hard filters; re-inspect the
> workbook when a requirement is missing from the initial candidates.

The key evidence rule was:

> Select every eligible diff cell an evaluator should inspect to verify the
> complete item. Do not stop after finding a final output row. When the item
> evaluates a calculation, include eligible changed cells for its named inputs
> or links, intermediate calculation rows, and resulting outputs.

It also added family completion:

> If one cell in a copy-across, copy-down, period, or scenario family is
> relevant, inspect its siblings and include every eligible sibling required by
> the rubric.

and a coverage audit:

> Confirm that each atomic requirement has selected evidence or that no
> eligible diff cell exists.

The prompt retained one guardrail:

> Do not include every transitive precedent merely because it feeds a formula.

### First Keysight result

| Metric | Before | Complete evidence |
|---|---:|---:|
| Precision | 99.36% | 97.56% |
| Recall | 58.78% | 93.17% |
| F1 | 70.20% | 94.60% |
| Exact item mappings | 21 / 103 | 63 / 103 |
| Entire omitted row families | 221 | 25 |

This was a large improvement on the workbook used to diagnose the original
failure.

### All-three result

| Example | Precision | Recall | F1 |
|---|---:|---:|---:|
| Keysight | 97.56% | 93.17% | 94.60% |
| Textron-1 | 58.37% | 97.89% | 68.80% |
| TopBuild | 54.68% | 98.25% | 66.06% |
| **Task macro** | **70.20%** | **96.43%** | **76.49%** |

The new prompt generalized poorly. Formula analysis showed:

- 92.6% of Textron false positives were direct formula precedents of a correct
  gold cell.
- 90.4% of TopBuild false positives were direct precedents.
- More than 96% of false positives on both were within two dependency hops.

The prompt's transitive-precedent warning was insufficient because the dominant
errors were direct inputs and intermediate rows, which the prompt explicitly
told the model to include.

### Decision

Preserve this behavior as the current complete-evidence baseline, but test a
much smaller evidence set with frozen Part 1 and Part 2 artifacts.

## 2. Policy modularization and minimal evidence

### Why this changed

The dominant error was no longer generic retrieval. The model correctly used
formula precedents for reasoning, then incorrectly returned those precedents as
mapped evidence.

The controlled experiment needed to change only the final evidence-selection
semantics while keeping the model and upstream artifacts fixed.

### Exact common-prompt refactor

The common Part 3 prompt was changed to distinguish:

> directly graded targets from operands, sources, contextual objects, periods,
> scenarios, and methods

It now says:

> Apply exactly one caller-selected part-3-policy-*.md reference to decide which
> eligible candidates become mapped evidence. Do not blend evidence policies.

and:

> Expand a copy-across, copy-down, period, or scenario family only after its
> evidence role is accepted, and only across the scope requested by the rubric.

The complete-evidence wording was preserved at the time in
`part-3-policy-current.md`.

### Exact minimal policy

The new `part-3-policy-minimal.md` said:

> Select the smallest eligible changed-cell set that lets an evaluator directly
> judge every requirement scored by the item.

Its defaults are:

> Default to the named target, result, or destination cells.

> Formula operands, source cells, precedents, and intermediate calculations are
> reasoning context, not mapped evidence merely because the condition names
> them or the target formula references them.

> Add a supporting assumption, control, source, or seed only when the rubric
> independently grades that object, its link, its value, or a method that the
> target cells alone cannot establish.

> For a direct-link requirement, map the changed destination cells; map source
> cells only when the source is separately graded.

It also added a pruning test:

> if removing it would not prevent the evaluator from judging a distinct scored
> requirement, remove it.

Sensitivity/Data Tables were kept as a special case because their table body,
axes, corner, and explicitly graded anchors can all be direct structural
evidence.

### Result

| Policy | Precision | Recall | F1 |
|---|---:|---:|---:|
| Complete evidence | 70.20% | 96.43% | 76.49% |
| Minimal evidence | 99.89% | 75.34% | 82.61% |

Per-workbook F1:

| Example | Complete | Minimal | Change |
|---|---:|---:|---:|
| Keysight | 94.60% | 69.31% | -25.29 |
| Textron-1 | 68.80% | 83.34% | +14.54 |
| TopBuild | 66.06% | 95.17% | +29.10 |

Minimal evidence almost eliminated false positives:

- Keysight: 64 to 5
- Textron: 1,278 to 0
- TopBuild: 1,167 to 1

But Keysight false negatives grew from 198 to 1,070.

### Diagnostic combination, not a prompt revision

A post-run analysis selected the complete-evidence output for items explicitly
assigning numerical credit and the minimal output for all other items. It scored
90.26% macro F1:

- Keysight: 92.27%
- Textron-1: 83.34%
- TopBuild: 95.17%

This was assembled deterministically from two existing prediction sets. It was
not a single model run and is not evidence that a scoring-aware prompt had yet
worked.

### Decision

The diagnostic identified a usable signal in rubric.json:

- Keysight had 87 of 103 items with numerical points and 75 items explicitly
  mentioning numerical credit.
- Textron had 10 of 101 items with numerical points.
- TopBuild had 16 of 149 items with numerical points.

The next prompt should choose evidence breadth per item from its scoring fields
instead of applying one workbook-wide threshold.

## 3. Scoring-aware v1

### Why this changed

Universal complete evidence was too broad for method-only rubrics. Universal
minimal evidence was too narrow for rubrics that separately score several named
numeric families. The prompt needed two item-level evidence modes.

### Exact change

The new policy classified an item as numerical-credit when numerical_points was
positive or its condition explicitly awarded numerical matching credit.

For those items it said:

> Include every directly named target or output family in the requested
> periods.

> Include directly named numeric component families when the item uses their
> values to define the graded total, bridge, roll-forward, or reconciliation.

> Include an explicitly graded assumption, source, control, seed, or link when
> the numerical or method credit depends on that object.

For method-only items it retained minimal selection:

> Default to the named target formula, result, or destination cells.

> Treat operands, source cells, precedents, and intermediate calculations as
> reasoning context unless the rubric independently grades that object.

The policy remained bounded to directly named objects and requested periods;
remote helpers and transitive dependency closure stayed prohibited.

### Result

| Example | Precision | Recall | F1 |
|---|---:|---:|---:|
| Keysight | 99.63% | 67.87% | 77.47% |
| Textron-1 | 100.00% | 75.03% | 83.04% |
| TopBuild | 99.87% | 93.19% | 95.05% |
| **Task macro** | **99.83%** | **78.69%** | **85.19%** |

This gained 8.70 F1 points over complete evidence and 2.58 points over minimal.
However, Keysight still had 713 false negatives. The model continued applying
minimal-style pruning inside numerical-credit items and returned only part of
many named line-item families.

### Decision

Make numerical completeness an explicit hard override, require every named
numeric family and requested period, and retain the dependency guardrail.

## 4. Scoring-aware v2

### Why this changed

v1 selected the correct evidence mode but did not follow it consistently for
Keysight. The instruction needed to prevent the method-only pruning rule from
leaking into numerical-credit items.

### Exact change

The prompt added:

> For these items, numerical-family completeness is a hard override: do not
> apply the method-only minimal-pruning rule.

It broadened the exact numerical rule to:

> Include every eligible changed cell in every directly named numeric line-item
> family across the requested periods or scenarios. This includes directly
> named inputs, links, components, intermediates, subtotals, and outputs.

It made each enumerated line item independent:

> Treat each line item enumerated by the rubric as a separately graded family;
> do not collapse the set to the final target, total, or output row.

It preserved the precision boundary:

> Formula dependency alone is not enough: do not include unnamed precedents,
> remote helpers, unrelated rows, or transitive dependency closure.

Finally, it added a checklist:

> make a checklist of every numeric family named in each numerical-credit item
> and confirm that every requested period or scenario is covered.

### Result

| Example | Precision | Recall | F1 | TP / FP / FN |
|---|---:|---:|---:|---:|
| Keysight | 97.59% | 87.78% | 90.55% | 2,102 / 53 / 287 |
| Textron-1 | 100.00% | 75.03% | 83.04% | 921 / 0 / 533 |
| TopBuild | 99.87% | 93.19% | 95.05% | 970 / 1 / 122 |
| **Task macro** | **99.15%** | **85.33%** | **89.55%** | — |

F1 progression:

| Policy | F1 |
|---|---:|
| Complete evidence | 76.49% |
| Minimal | 82.61% |
| Scoring-aware v1 | 85.19% |
| **Scoring-aware v2** | **89.55%** |

v2 gained 13.06 F1 points over complete evidence and 4.36 points over v1.
Keysight produced the main gain, from 77.47% to 90.55% F1.

### Decision

Promote scoring_aware v2 to the default.

## Controllable JSON and summary context

Part 3 can now receive no upstream context, Part 1 context, or the complete Part
1 plus Part 2 context. The JSON channel carries `sections.json`,
`subsections.json`, and `subsection_index.json`; the summary channel carries only
the Part 1 `summary.md`. Supplied artifacts are validated against their lineage
before filtering, and JSON coordinates remain authoritative.

This transport/context change is implemented but unmeasured. The 89.55% result
above used earlier frozen upstream artifacts and must not be attributed to the
new Markdown context.

## 5. Conditional visual structural evidence

### Why this changed

Part 3 occasionally needs layout context for directly named rubric structures,
but visual similarity must not weaken the exact diff, object-binding, scope, or
evidence-role rules. The optional tool therefore needed an explicitly narrower
role than in Parts 1 and 2.

### Exact change

Part 3 now has a complete
[`part-3-workflow-visual.md`](../../skills/xlsx-rubric-mapping/references/part-3/part-3-workflow-visual.md)
variant. It permits a bounded viewport only after programmatic diff and
retrieval for unresolved multi-level headers, sensitivity-table structure,
merged labels, or visually separated candidate families. A screenshot cannot
determine eligibility, prove rubric binding, establish formula method or
dependency, or justify expanding a mapping because cells look related. The
runtime exposes this variant under the canonical `part-3-workflow.md` name only
when the visual tool is attached.

### Measurement status

Implemented and covered by prompt-routing tests. The 89.55% scoring-aware v2
result predates this addition, so it remains historical evidence for the prior
prompt and must not be attributed to visual inspection. A controlled rerun must
record whether the tool was actually called.

## Current state

The effective Part 3 prompt is composed from:

1. Either normal [part-3-workflow.md](../../skills/xlsx-rubric-mapping/references/part-3/part-3-workflow.md)
   or complete visual
   [part-3-workflow-visual.md](../../skills/xlsx-rubric-mapping/references/part-3/part-3-workflow-visual.md),
   exposed under the canonical `part-3-workflow.md` name
2. [output-format.md](../../skills/xlsx-rubric-mapping/references/part-3/output-format.md)
3. The shared workbook-inspection rules in the skill entrypoint
4. The shared hosted output-path instruction

The runtime evidence selector was retired when the references were
consolidated. The scoring-aware v2 behavior is now the sole Part 3 instruction.

The strongest comparison used gpt-5.6-sol with identical frozen Part 1 and
Part 2 artifacts for every Part 3 policy. This isolates the Part 3 prompt
change. It is development-set performance on the three known examples, not an
unbiased held-out generalization estimate.

## Evidence used

- Codex task "Run part one with LangSmith" (2026-08-17)
- Codex task "Review three-stage extraction" (2026-08-17)
- ChatGPT chat "Pipeline design analysis" (2026-08-17)
- Saved predictions under artifacts/ablations
- Saved evaluations under artifacts/evaluations
- Local ignored report retained at
  `artifacts/reports/prompt-v2-all-three-2026-08-17.md`
- Current prompt files and the committed baseline in Git
