# Part 2: intermediate subsections

Part 2 refines workbook semantics in service of Part 3. It is not directly labeled, and it must remain useful without a rubric. Do not pass `rubric.json` into subsection creation.

## Represent multiple semantic axes

Within each Part 1 section, classify cells along axes that commonly change what a grading item refers to:

- historical actuals versus projected periods;
- hardcoded inputs and assumptions versus formula-derived outputs;
- linked or imported source data versus locally calculated values;
- controls and model settings versus analytical schedules;
- labels and period headers versus gradeable values or formulas;
- base-case, scenario, sensitivity, or outlook variants;
- calculations, subtotals, checks, key outputs, metadata, and explanatory notes.

These are tags, not a universal fixed taxonomy. Infer them from period labels, cell types, formula dependencies, formats, nearby text, and task instructions.

## Use a primary partition plus semantic tags

Prefer a stable primary subsection membership for each relevant cell, then attach multiple semantic tags. This is easier to reason about than creating many overlapping subsections for every analytical view. Allow an explicit secondary link only when one cell genuinely bridges two objects.

Subsections do not have to be rectangular or contiguous. Their shapes must still be explainable and reversible to exact cells. Avoid shapes created only to improve one labeled example.

Do not force blank cells into a subsection merely to complete a rectangle. For example, when historical columns contain actual values and scenario columns intentionally do not apply, leave the non-applicable cells out. Conversely, retain blank template cells when their role is real and future completion is expected.

## Required project handoff artifact

The assignment does not require a Part 2 function or evaluator schema. This project deliberately defines `create_intermediate_sections(...) -> subsections.json` so Part 2 can run independently and hand a compact artifact to Part 3:

```json
{
  "subsections": [
    {
      "subsection_id": "subsection_001",
      "parent_section_id": "section_001",
      "sheet": "Model",
      "cells": ["B4", "C4"],
      "roles": ["historical", "input"]
    }
  ]
}
```

Keep labels, periods, formula signatures, evidence, and confidence in traces or the reproducible workbook map rather than duplicating them in this handoff. Store only exact cells, the Part 1 parent, and stable semantic roles in `subsections.json`.

## Validate Part 2 by downstream utility

Because there is no gold subsection artifact, measure whether the representation improves Part 3 precision, recall, F1, mapped-item coverage, latency, and cost. Also inspect:

- the share of diff cells attached to a subsection;
- contradictory semantic tags;
- subsection size and fragmentation distributions;
- stability under removal of formatting or instruction signals;
- whether item retrieval needs fewer irrelevant candidate cells.

Keep Part 2 only if it improves mapping quality or materially improves traceability at acceptable cost.
