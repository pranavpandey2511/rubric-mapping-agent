# Design Notes

These notes capture how the Rubric Mapping Agent was designed and iterated. The
goal was a small, testable system for the three-part workbook-mapping task, not
a general spreadsheet-agent platform.

## 1. Starting point

I began with a baseline question: which parts should be deterministic, and
which parts need model judgment? Exact workbook coordinates and output schemas
are deterministic concerns; understanding financial sections, subsection
meaning, and rubric intent requires semantic reasoning.

### GPT models and Deep Agents

I chose GPT models because the project already had OpenAI API access. I used
Deep Agents as the orchestration layer because it provides the agent loop,
tool binding, skill loading, a virtual filesystem, and structured responses.
That reduced boilerplate and left more time for workbook representation,
prompt experiments, and evaluation. Deep Agents can also support shell-style
tools, but this implementation intentionally exposes only hosted Python.

### Hosted Code Interpreter

Each agent invocation receives OpenAI's hosted Code Interpreter as its Python
tool. The runtime creates a fresh container, disables its network, uploads only
the declared stage inputs, downloads the declared JSON outputs, and attempts to
delete the container in `finally`. The agent does not receive a local shell.

### Spreadsheet and task skills

I created two complementary skill layers:

- a general Excel skill for safe, coordinate-aware workbook inspection,
  informed by the workflow patterns in OpenAI and Claude spreadsheet skills;
- a project-specific rubric-mapping skill with separate Part 1, Part 2, and
  Part 3 workflows and exact output contracts.

At runtime, the virtual filesystem contains the Excel skill and only the
current stage's rubric-mapping references. This keeps the context focused and
prevents Part 3 rubric instructions from entering Parts 1 or 2.

## 2. Initial pipeline

The first implementation used three explicit stages with file handoffs. Both
of the first two stages initially produced a JSON artifact and a Markdown
summary:

| Stage | Responsibility | Initial outputs |
| --- | --- | --- |
| Part 1 | Find overall financial-model sections | `sections.json`, `summary.md` |
| Part 2 | Build rubric-independent retrieval units | `subsections.json`, `summary.md` |
| Part 3 | Map every rubric item to eligible changed cells | `items_to_cells.json` |

Each stage uses a new agent conversation and container. Parts 1 and 2 never
receive `rubric.json`; it enters only in Part 3. Host code validates schemas,
worksheet scope, parent relationships, rubric IDs, and Part 3 diff eligibility
before publishing artifacts.

I first ran Part 1 alone to understand the evaluator and its sensitivity to
over-merging versus over-splitting. I then ran the complete pipeline on all
three development workbooks to identify where downstream quality was being
lost. The full baseline is recorded in the README: Part 1 reached 90.60%
task-macro F1, Part 2 covered 99.97% of eligible diff cells, and the initial
complete-evidence Part 3 policy reached 76.49% task-macro F1.

## 3. Improving the handoffs

The initial pipeline paired both Part 1 and Part 2 JSON with coordinate-free
Markdown summaries. The Part 1 summary was useful and remained in the design.
The Part 2 summary did not provide sufficiently structured retrieval context
for Part 3. After reviewing the early results, I followed Codex's suggestion to
replace that summary with a machine-readable subsection index.

### Part 1 summary

Part 1 has produced evaluator-compatible `sections.json` plus a coordinate-free
`summary.md` since the initial pipeline. The summary gives each section a title,
technical description, and plain-language explanation. Part 2 and Part 3 can
use it for orientation, while JSON remains the source of coordinate truth.

### Part 2 retrieval index

Part 2 now writes two JSON files:

- `subsections.json` contains the exact subsection membership and roles;
- `subsection_index.json` organizes those subsections into semantic families
  with metadata and direct typed relationships for Part 3 retrieval.

This replaced the original Part 2 `summary.md` output after the prose handoff
did not work well enough for downstream retrieval. The retrieval-oriented
prompt reduced the noisy Keysight representation from 451 to 177 subsections
and removed separator-only groups without reducing diff coverage. Across all
three workbooks it produced 450 subsections, zero separators, and 99.97%
eligible-diff coverage.

The richer handoffs were useful during later Part 3 work, but their independent
quality contribution has not been isolated. A clean `part1_part2` versus
`part1` versus `none` context ablation is still required.

## 4. Prompt and workflow experiments

Most quality gains came from changing stage instructions and controlling the
effective context rather than adding application layers.

### Part 1: local sections and sheet context

The early Part 1 prompt was conservative and under-grouped. Broad hierarchy
rules then over-merged unrelated panels. The strongest approach was to identify
the smallest complete local panel, audit all four edges, and give each worksheet
a fresh invocation. A focused study reached 89.83% task-macro F1; a later full-
pipeline run reached 90.60%.

Later hierarchy/responsibility and union-of-bands experiments scored 88.99% and
86.30% respectively, so both were rejected and the local-panel policy was
restored.

### Part 2: retrieval rather than taxonomy

The original Part 2 output contained too many small groups, open-ended roles,
and separator-only subsections. The revised policy groups coherent financial
concepts and formula families, uses a controlled role vocabulary, and keeps
relationships only when the workbook provides direct evidence. Part 2 has no
gold artifact, so these are structural diagnostics rather than a semantic F1
claim.

### Part 3: evidence breadth

The initial mapper favored small evidence sets and missed complete named
families. A complete-evidence prompt fixed recall but added many formula
precedents, reaching 76.49% task-macro F1. Using identical frozen Part 1/2
artifacts, the controlled policy progression was:

| Part 3 policy | Task-macro F1 |
| --- | ---: |
| Complete evidence | 76.49% |
| Minimal evidence | 82.61% |
| Scoring-aware v1 | 85.19% |
| Scoring-aware v2 | 89.55% |

The current scoring-aware rule is broad for directly named numerical-credit
families and minimal for method-only items. It still excludes unnamed
precedents, remote helpers, and transitive dependency closure.

## 5. Configurable stage scope

Every stage supports `sheet` or `workbook` scope through environment variables.
The current defaults are:

```dotenv
RUBRIC_MAP_PART1_SCOPE=sheet
RUBRIC_MAP_PART2_SCOPE=workbook
RUBRIC_MAP_PART3_SCOPE=workbook
```

Sheet scope gives each worksheet a fresh context and combines validated outputs
deterministically. Part 1 uses it by default because this produced the clearest
measured gain. Part 2 and Part 3 sheet paths are implemented and tested but are
not the default; their quality and cost trade-offs still need controlled study.

Sheet scope is a context and output boundary, not physical worksheet isolation:
the complete workbook files are uploaded. The prompt restricts the target
worksheet and the host rejects cross-sheet output, but the runtime cannot prove
that the model never read another sheet.

## 6. Optional visual inspection

I added a read-only `inspect_workbook_view` tool backed by LibreOffice. It can
render a bounded cell range through a headless PDF-to-PNG path or a visible Calc
viewport. The feature is controlled by `RUBRIC_MAP_VISUAL_BACKEND` and is off by
default.

The tool is intended only for unresolved layout questions such as merged
headers, whitespace, repeated axes, or panel boundaries. OpenPyXL and OOXML
remain authoritative for exact coordinates. Early exploration did not show a
measured improvement, so the visual path remains optional. The current code has
local smoke-test coverage, but still needs a controlled benchmark that records
whether the model called the tool and how the scores changed.

## 7. Current code boundaries

- `workflow.py` owns the public stage functions and orchestration.
- `runtime/` owns Deep Agent construction, skill bundling, hosted containers,
  uploads, downloads, and cleanup.
- `stage_outputs.py`, `handoff.py`, and `retrieval_index.py` validate artifacts
  and cross-stage context.
- `skills/` contains the general Excel and stage-specific mapping guidance.
- `visual/` contains the optional LibreOffice inspection backends.
- `review/` creates a deterministic annotated workbook for human inspection;
  it is separate from the agent's visual tool.
- `scripts/` contains managed runs, evaluation, and controlled ablations.

This decomposition keeps model judgment inside explicit stages and keeps
validation, evaluation, and artifact publication deterministic.

## 8. Next steps

The highest-value next step is to build a stronger harness for each stage
independently. Each harness should make context budgets, specialist sub-agents,
delegation, retries, traces, and stage-specific evaluation explicit instead of
expanding one general agent.

The next experiments should:

1. freeze upstream artifacts and compare sheet versus workbook scope per stage;
2. isolate the value of `summary.md` and `subsection_index.json` for Part 3;
3. rerun the visual tool as a controlled ablation with actual tool-call logs;
4. add stronger retry, timeout, failure-manifest, and artifact-lineage checks;
5. validate the selected defaults on a broader held-out workbook set.

All reported scores currently come from three known development workbooks.
They demonstrate iteration, not unbiased production accuracy.
