# Part 2 mapping workflow

Part 2 divides each Part 1 section into compact, rubric-independent semantic
subsections:

```text
create_intermediate_sections(
    input.xlsx,
    complete.xlsx,
    instructions.md,
    sections.json,
    summary.md,
) -> subsections.json + subsection_index.json
```

`input.xlsx` is the starting workbook given to a human. The human follows
`instructions.md` to produce `complete.xlsx`, the completed workbook. Treat them
as the before-and-after states of the same task: use `complete.xlsx` to understand
the finished work, `input.xlsx` to identify what the human added or changed, and
unchanged cells as supporting context.

A subsection is a coherent financial concept, formula family, schedule
component, control, check, or output that can be retrieved as one meaningful
unit during item-to-cell mapping. It is not merely a visual row, a formatting
block, a rectangle, or an exhaustive label for every cell in the parent
section.

For every subsection, extract:

- a unique subsection ID;
- its Part 1 parent section ID;
- the exact worksheet name;
- the exact A1 cells that implement the concept; and
- one or more roles from the fixed role taxonomy below.

IDs must already be unique across the workbook so sheet-scoped outputs can be
concatenated without rewriting. Determine the worksheet's one-based position in
workbook order and use:

- `subsection_s<sheet-position-3-digits>_<within-sheet-3-digits>`; and
- `<subsection-id>_family_<within-subsection-2-digits>`.

For example, the second subsection on the third worksheet is
`subsection_s003_002`; its first family is
`subsection_s003_002_family_01`. Assign within-sheet numbers deterministically
in Part 1 parent order, then by the subsection's top-left cell and semantic
order. Use this same convention in workbook- and sheet-scoped invocations.

Also author the structured retrieval index used by Part 3. Split each
subsection's changed cells into precise named financial or formula families and
record object names, aliases, period scope, anchors, calculation behavior,
normalized formula signatures, and only direct family relationships. This
agent-authored index replaces the Part 2 Markdown summary.

Depending on the pipeline handoff policy, Part 2 may receive Part 1
`sections.json`, Part 1 `summary.md`, or both. At least one is always present.
When only the summary is
present, it supplies section IDs and semantic orientation, but no geometry;
re-identify the parent footprints from the workbooks. When JSON is present, its
explicit cells are authoritative.

## Follow the declared execution scope

The user message declares `EXECUTION_SCOPE` for this invocation.

- In `sheet` scope, process and emit subsections and index families only for
  Part 1 parents on `TARGET_SHEET`.
- In `workbook` scope, process every supplied Part 1 parent and emit one
  workbook-wide subsection and index bundle.

The output schema and workbook-unique ID convention are identical in both
modes. Never emit a cell owned by another worksheet in sheet scope.

## Work inside the Part 1 boundaries

Process one Part 1 section at a time. Every subsection cell must belong to its
declared parent section on the same worksheet.

When supplied, use the Part 1 title, detail, and plain-language explanation to
understand the parent's intended financial purpose. Use explicit cells from
`sections.json` when it is supplied; otherwise rediscover the exact parent
footprint by inspecting the input and completed workbooks. Semantic prose may
guide interpretation, but it cannot establish a coordinate or override the
parent footprint encoded by validated JSON cells. The host retains the
authoritative Part 1 JSON and validates every emitted Part 2 cell against it,
even when that JSON was withheld from the agent for an ablation.

Inspect both workbook states and retain exact coordinates, raw formulas, cached
values when available, local labels, period headers, styles, merged ranges, and
formula dependencies. Identify cells added or changed in `complete.xlsx`, but
also inspect unchanged labels and headers needed to interpret those cells.

## Use attached visual inspection for semantic grouping ambiguity

When `inspect_workbook_view` is attached, use it selectively after structural
inspection when layout can clarify a subsection decision. Inspect a bounded
viewport around the relevant Part 1 parent to understand multi-level headers,
explicit historical/projected or scenario bands, merged labels, control and
check placement, or whether separated groups visually belong to one named
object. Compare matching `input` and `complete` regions when the layout change
helps interpret the completed model.

Visual evidence may support semantic grouping, but it cannot expand the Part 1
parent, establish exact membership, or turn formatting and proximity into a
financial relationship. Confirm every chosen cell, formula family, period
scope, role, and relationship from workbook structure and contents. Do not call
the tool when those structural signals already resolve the grouping.

## Form coherent retrieval units

Group cells by the financial object they implement and by their calculation
behavior.

Treat the Part 1 parent as a bounding region, not as a proposed subsection.
Re-segment its contents independently; a broad parent title or footprint is not
evidence that its cells form one retrieval unit.

- Keep copy-across or copy-down formula families together when they represent
  the same line item within one period regime, scenario, entity, or category.
- Keep a small set of related rows together when they jointly implement one
  named calculation, schedule, control, check, or output.
- Keep an identifying row or column label with the value or formula family it
  identifies.
- Keep local period or scenario headers when they are necessary to interpret a
  family; shared global headers may remain separate context.
- Treat explicit historical/actual and projected/forecast period bands as
  subsection boundaries. Do not place cells from both bands in one subsection;
  create period-specific subsections even when they describe the same financial
  concept. A shared identifying label may belong to both when needed.
- When period bands are not explicit, separate historical and projected cells
  when their data source or calculation behavior differs.
- Separate hard-coded assumptions, linked values, local calculations,
  controls, checks, and outputs when each is independently meaningful.
- Keep a control or check separate from a broader calculation or output block
  unless the cells are genuinely inseparable evidence for one object.
- Separate formula families that have different sources, purposes, or
  propagation patterns even when they are visually adjacent.
- Combine small adjacent groups when they jointly express one concept and
  separating them would make either group incomplete.
- Allow non-contiguous cells only when they clearly implement the same
  financial object and the gap contains unrelated cells or layout space.

Do not copy the complete Part 1 footprint into one subsection unless the entire
parent genuinely represents one indivisible concept.

## Assign cell membership

Prefer one primary subsection for each relevant cell. Give a cell a second
membership only when it genuinely bridges two financial objects, such as a
shared local label or control used as direct evidence for both groups.

Do not create subsections solely for:

- blank separators or whitespace;
- decorative formatting;
- borders without semantic content;
- isolated headers that do not identify a retrievable object; or
- arbitrary fixed-size row or column chunks.

Omit ordinary blanks and spacer cells. Retain a blank only when its blank state
is meaningful—for example, an intentional input, template slot, or future-
period modeling cell. A subsection does not need to be rectangular.

Relevant cells added or changed in `complete.xlsx` should be reachable through
at least one meaningful subsection unless they cannot be assigned without
inventing a false semantic group.

## Author the Part 3 retrieval index

Compute the exact input-to-complete diff programmatically. Inside every
subsection that contains eligible changed cells, partition those changed cells
into the smallest complete families that Part 3 can retrieve independently.
Do not default to one family per subsection, and do not mechanically create one
family per row when several rows implement one named object.

For every family:

- use the workbook-native line-item, schedule, control, check, or calculation
  name as `object_name`;
- add only genuine alternative names or task-language variants as `aliases`;
- place every eligible changed implementation cell in exactly one family's
  `changed_cells`;
- use `anchor_cells` only for unchanged labels or headers already included in
  the parent subsection;
- preserve the narrowest applicable roles from the subsection;
- distinguish `historical`, `projected`, and `unspecified` period scope and
  record the exact nearby period header cells and labels when available;
- describe the physical family as `row`, `column`, `block`, or
  `non_contiguous`;
- classify behavior as `input`, `assumption`, `linked`, `calculation`,
  `control`, `check`, `output`, `header`, `template`, `sensitivity`, or
  `value`; and
- record compact normalized formula signatures for formula families. Normalize
  copy-across or copy-down references to relative R/C offsets so equivalent
  formulas share a signature; use an empty list for non-formula families.

Add a relationship only when workbook formulas, an explicit roll-forward, or
an unambiguous shared object proves a direct connection:

- `feeds`: the source family directly supplies a same-workbook calculation;
- `linked_to`: the target is directly linked to the source, especially across
  worksheets or schedules;
- `component_of`: the source is an explicitly named component of the target;
- `paired_with`: the families are historical/projected or otherwise explicit
  period-regime versions of the same financial object.

Relationships are retrieval paths, not permission to include every neighbor.
Do not infer transitive relationships, create proximity-based links, or connect
families merely because they share formatting.

In a sheet-scoped invocation, emit relationships only between families emitted
by that invocation. Do not invent a remote family ID. Part 3 can inspect the
workbook directly when a cross-sheet relationship is not represented.

## Use the fixed role taxonomy

Assign only roles that describe the subsection's actual function:

- `historical`: reported or prior-period information;
- `projected`: forecast or forward-period information;
- `input`: a directly entered model input;
- `assumption`: a value used to drive calculations;
- `linked`: a value or formula sourced from another cell, sheet, or schedule;
- `calculation`: a locally computed value or formula family;
- `control`: a selector, switch, seed, toggle, or model-control mechanism;
- `output`: a result presented for use or interpretation;
- `check`: an error check, balance check, reconciliation, or validation result;
- `header`: identifying labels or axes that form meaningful retrieval context;
- `template`: intentionally prepared cells for future entry or extension;
- `scenario`: scenario-specific inputs, calculations, or outputs; and
- `sensitivity`: cells that define or populate a sensitivity analysis.

Use only these role names. Apply multiple roles when they describe independent
dimensions of the same subsection, such as `projected` plus `calculation` or
`historical` plus `linked`. Do not invent synonyms or workbook-specific tags.
Roles must describe the subsection as a whole. If different roles apply to
different subsets of its cells, split those subsets into coherent subsections
instead of attaching every role to the combined block.

## Final checks

Before writing the result, confirm that:

- every subsection has a unique deterministic ID;
- every parent section exists on the same worksheet;
- every cell lies inside its declared parent;
- repeated formula families were not accidentally split within one period
  regime or scenario;
- no subsection crosses an explicit historical/actual versus
  projected/forecast period boundary;
- each role describes the subsection's complete cell set rather than only a
  subset of its cells;
- distinct financial objects were not collapsed into one oversized unit;
- no subsection contains only separators, decorative cells, or meaningless
  blanks;
- adjacent tiny subsections are combined when they implement one concept;
- relevant changed cells are retrievable through meaningful units; and
- every role belongs to the fixed taxonomy;
- every eligible changed subsection cell appears in exactly one index family;
- every anchor belongs to its declared subsection and is never treated as a
  changed cell;
- family scopes and names preserve explicit historical/projected distinctions;
  and
- every relationship is direct, typed, and references existing family IDs.

Follow [output-format.md](output-format.md) exactly.
