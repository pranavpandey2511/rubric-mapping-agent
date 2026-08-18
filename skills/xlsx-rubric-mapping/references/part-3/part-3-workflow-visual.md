# Part 3 mapping workflow

Part 3 maps every rubric item to the exact workbook cells that directly satisfy
or demonstrate that item:

```text
create_items_to_cells_mapping(
    input.xlsx,
    complete.xlsx,
    instructions.md,
    rubric.json,
) -> items_to_cells.json
```

`input.xlsx` is the starting workbook given to a human. The human follows
`instructions.md` to produce `complete.xlsx`, the completed workbook. Treat them
as the before-and-after states of the same task: use `complete.xlsx` to understand
the finished work, `input.xlsx` to identify what the human added or changed, and
unchanged cells as supporting context.

For every rubric item, extract the eligible changed cells that directly satisfy
or demonstrate each stated requirement. Cover every explicitly required value,
line item, method, link, period, scenario, or sensitivity structure, but do not
include unrelated helpers or formula precedents.

## Follow the declared execution scope

The user message declares `EXECUTION_SCOPE` for this invocation.

- In `sheet` scope, include every rubric item exactly once but emit eligible
  cells only from `TARGET_SHEET`; use an empty cell list when that sheet has no
  evidence for an item.
- In `workbook` scope, search all worksheets and emit one workbook-wide mapping.

Never emit a cell owned by another worksheet in sheet scope. The orchestrator
combines sheet-scoped item evidence and validates the final workbook mapping.

## Build the eligible-cell universe

Compare `input.xlsx` and `complete.xlsx` by exact worksheet name and cell
address. A cell is eligible when its content in `complete.xlsx` is absent or
different in `input.xlsx`.

Treat these as changes when applicable:

- a blank cell becomes a value or formula;
- a value changes type or content;
- raw formula text changes, even if the displayed or cached result is the same;
- a formula replaces a constant or a constant replaces a formula; or
- a meaningful empty string differs from a truly empty cell.

Compare raw values and raw formulas, not rendered values alone. Preserve enough
evidence for each eligible cell to reason about:

- worksheet and exact A1 address;
- input and completed contents;
- raw and normalized formula form;
- nearby row, column, period, and scenario labels;
- copy-across or copy-down family membership;
- financial and semantic role;
- containing Part 1 section or Part 2 subsection when available; and
- direct formula dependencies and dependents.

Only eligible changed cells may appear in the final mapping. Unchanged labels,
headers, sources, and formulas may be used to understand a requirement but may
not be emitted.

## Parse every rubric item

Enumerate every `item_id` in rubric order and include it exactly once. Read the
entire item, including its description, conditions, points, numerical points,
partial-credit rules, deductions, and notes.

Break each condition into atomic requirements. For each requirement, identify:

1. the directly graded target or financial object;
2. any separately graded input, assumption, link, control, source, or method;
3. the required period, scenario, entity, category, or worksheet scope;
4. whether the item grades numerical values, formula method, linkage,
   structure, or some combination of these; and
5. what changed-cell evidence would directly demonstrate compliance.

Do not stop after finding evidence for only the first clause or the final total.
Account for every named requirement before finalizing the item's cells.

## Choose one evidence mode for every rubric item

Classify each rubric item as a whole as either `numerical-complete` or
`method-minimal`. An item cannot mix modes across its atomic requirements.

An item is `numerical-complete` when it has any positive `numerical_points`,
explicitly awards numerical credit, or requires named values to match the
completed workbook. Any positive numerical allocation is sufficient. For such
an item, every numeric object named anywhere in the item must use
`numerical-complete`, including objects in clauses that also grade formula
construction, linkage, or method.

Do not weaken or ignore the numerical rule because the numerical allocation is
small, method points are larger, or only one clause explicitly discusses value
accuracy. Never apply `method-minimal` pruning anywhere within a
`numerical-complete` item.

An item is `method-minimal` only when the entire item has zero
`numerical_points`, contains no explicit numerical-credit or numerical-matching
requirement, and grades only formula construction, linkage, structure, or
methodology.

## Retrieve candidate evidence

Use the item language, workbook labels, formula signatures, dependencies, and
financial meaning to retrieve candidates from the eligible-cell universe.
Part 1 sections and Part 2 subsections may narrow the search when supplied.
The Part 1 summary may provide coordinate-free semantic orientation. The Part 2
agent-authored retrieval index provides names, aliases, roles, period scope,
formula signatures, and direct relationships over explicit Part 2 geometry.
Every supplied artifact is retrieval context rather than a mandatory semantic
boundary; explicit JSON cells remain authoritative when present. Re-inspect the
workbook whenever a named requirement is missing from the initial candidates
or JSON geometry was withheld by the handoff policy.

When `subsection_index` is supplied, use it as the primary structured retrieval
index over the Part 2 geometry. Load and query it programmatically; do not dump
or read the entire file as undifferentiated prose. Its `families` divide broad
subsections into independently named row or formula families:

- match each atomic rubric object against `object_name` and `aliases`, preferring
  exact workbook-native language before broader semantic similarity;
- require compatible `scope`, including historical/projected period type and
  any available period headers, before accepting a family;
- treat `changed_cells` as candidate evidence and `anchor_cells` only as labels
  or headers for interpretation; never emit an anchor merely because it appears
  in the index;
- use `calculation_kind`, `roles`, and `formula_signatures` to distinguish
  inputs, links, local calculations, controls, checks, and outputs;
- retrieve complete changed-cell families for directly named numerical objects
  across every requested period; and
- retain the family ID beside each atomic requirement until the item's coverage
  audit is complete so evidence distributed across several subsections is not
  silently dropped.

After exact family matching, inspect at most one relationship hop from each
accepted family. Follow `paired_with` only when the item requests both period
regimes or a historical-to-forecast method. Follow `linked_to`, `feeds`, or
`component_of` only when the related object, source, destination, component, or
calculation is explicitly named by the rubric or is needed to resolve an
otherwise unmatched named clause. A relationship is a retrieval path, not
object-binding evidence by itself. Do not add every neighbor or dependency.

Before falling back to a broad workbook search, make a retrieval ledger with one
row per atomic requirement: named object, requested scope, matched family IDs,
accepted changed cells, and unresolved reason. Search the workbook directly for
every unresolved row, and never finalize an item while a directly named
object-and-scope combination remains unexplained.

Accept a cell's evidence role before expanding to its siblings. Then expand
only across the periods, scenarios, entities, or categories requested by the
rubric. Similar formatting or formula shape alone does not make an entire
family relevant.

## Use attached visual inspection only for structural ambiguity

When `inspect_workbook_view` is attached, use it only after the programmatic
diff and structured retrieval steps when layout is still needed to interpret a
directly named rubric object. Suitable cases include multi-level period or
scenario headers, a sensitivity table's axes, body, and corner anchor, merged
labels spanning several candidate families, or visually separated regions whose
structural relationship remains unclear. Compare matching `input` and
`complete` viewports when that distinction is material.

The screenshot cannot determine whether a cell is eligible, prove object or
scope binding, establish formula method or dependency, or justify expanding a
mapping because cells look related. Resolve those decisions from raw workbook
contents, formulas, the exact input-to-complete diff, and the rubric. Do not use
the tool when those sources already settle the requirement.

## Bind every emitted cell to the rubric

An object is directly named when the rubric explicitly identifies the
financial line item, calculation, assumption, control, source, link, subtotal,
or output. Objects enumerated as operands in a required equation, bridge,
roll-forward, or reconciliation are directly named.

An object is not directly named merely because its cell feeds a named formula,
appears in the same schedule, section, or subsection, shares a formula pattern
or format, or is financially related but absent from the rubric language.

A candidate cell may be emitted only when all four tests pass:

1. **Eligibility:** it belongs to the input-to-complete diff.
2. **Object binding:** its row, label, formula role, or control directly
   represents an object named by the atomic requirement.
3. **Scope binding:** its period, scenario, entity, or category is requested.
4. **Evidence-role binding:** it directly demonstrates a graded value, method,
   destination, named component, assumption, link, control, or output.

Formula dependency, physical proximity, shared formatting, matching formula
shape, or section or subsection membership cannot satisfy object binding by
themselves.

## Select numerical evidence

For every `numerical-complete` item, numerical-family completeness is a hard
override. Do not apply the `method-minimal` pruning rule to any requirement in
that item.

Before selecting cells, enumerate every directly named numeric family, every
requested period, scenario, entity, or category, and whether the named object
is a target, component, subtotal, input, link, control, assumption,
intermediate, or output directly graded by the requirement. Then:

- include every eligible changed cell in every directly named numeric line-item
  family across the requested periods, scenarios, entities, or categories;
- treat each line item named in an equation, bridge, roll-forward, or
  reconciliation as a separate family rather than replacing component rows
  with only a final total;
- include explicitly graded assumptions, sources, controls, seeds, links, and
  output values;
- include all directly graded components of a calculation when the rubric
  assigns value credit to those components; and
- verify family completeness row by row and period by period.

The size of `numerical_points` does not affect this rule.

Do not add unnamed precedents, remote helper calculations, unrelated rows, or
the transitive dependency closure. A formula dependency is reasoning context;
it becomes mapped evidence only when the rubric grades that cell or financial
object directly.

## Select method and linkage evidence

For every `method-minimal` item that grades a calculation method, formula
construction, or direct link without separately grading every operand:

- map the eligible target, result, or destination formula cells that directly
  demonstrate the method;
- treat operands, source cells, precedents, and intermediate calculations as
  reasoning context unless the rubric independently grades them;
- for a direct-link requirement, map the changed destination cells and include
  source cells only when the source itself is separately graded;
- include one complete requested copy-across or copy-down target family when
  the method must hold across several periods or scenarios; and
- exclude a supporting cell if removing it would not prevent a distinct stated
  requirement from being judged.

These method-only mappings must remain limited to direct evidence for the
graded method, linkage, structure, or destination.

When a `numerical-complete` item contains both numerical and method clauses,
complete every named numerical family and include the direct method evidence.
Do not reinterpret any clause in that item as `method-minimal`.

## Handle sensitivity analyses

For an explicitly required Excel sensitivity analysis or Data Table, identify
the complete directly required structure. Depending on the rubric, this may
include:

- the table body containing calculated results;
- row-axis input values;
- column-axis input values;
- the corner formula or anchor cell;
- linked output or input anchors; and
- scenario or control cells explicitly named by the item.

Include only eligible cells and only the structural elements the rubric requires.
Do not map an entire surrounding section merely because it contains the table.

## Resolve special cases

- A cell may map to more than one item when it directly satisfies distinct
  rubric requirements.
- An item may have an empty cell list only when no eligible changed cell
  directly demonstrates any of its requirements.
- Do not map a whole section or subsection when the item concerns a smaller
  line-item, formula, period, or scenario family.
- Do not infer relevance from proximity, formatting, or dependency alone.
- Do not substitute a final output for separately named component families.
- Do not add unchanged cells merely because their labels or formulas explain a
  changed target.

## Final two-pass selection audit

Perform these passes in order after the initial mapping.

### Pass 1: remove unsupported candidates

- Remove unnamed precedents, remote helpers, unrelated rows, transitive
  dependencies, and cells admitted only through proximity, formula shape, or
  section or subsection membership.
- For `method-minimal` requirements, retain only direct target, result,
  destination, or separately graded control evidence.
- Confirm that every retained cell passes eligibility, object binding, scope
  binding, and evidence-role binding.

### Pass 2: check requirement coverage

- Recheck every `numerical-complete` item after removing unsupported candidates.
- Make a checklist of every named numeric family and confirm that every
  requested period, scenario, entity, or category is represented.
- Restore any qualifying named-family cell incorrectly removed by method-style
  pruning.
- Do not finalize while a named family-and-scope combination remains
  unexplained.

When the passes conflict, numerical completeness wins only for cells that pass
the object-binding and scope-binding tests.

Before writing the result, also confirm that every rubric `item_id` appears
exactly once, every coordinate exists in `complete.xlsx`, every cell is
eligible, every atomic requirement has evidence or a confirmed absence of
eligible evidence, no broad unrelated region was mapped, duplicates are
removed, and items and cells use deterministic ordering.

Follow [output-format.md](output-format.md) exactly.
