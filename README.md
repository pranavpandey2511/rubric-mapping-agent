# Rubric Mapping Agent

An agentic pipeline that inspects an input/completed Excel workbook pair and
produces three mapping layers:

1. Part 1: overall sections (`sections.json` and `summary.md`)
2. Part 2: retrieval-oriented subsections (`subsections.json` and
   `subsection_index.json`)
3. Part 3: rubric-item-to-cell mappings (`items_to_cells.json`)

The runtime uses GPT models through the OpenAI API, Deep Agents, and a fresh
hosted Code Interpreter container for each workbook- or sheet-scoped
invocation.

## Setup

```bash
# Create the local configuration file, then add OPENAI_API_KEY.
cp .env.example .env

# Install the locked project environment.
uv sync --locked
```

Every non-dry run makes paid OpenAI model and Code Interpreter calls. Runtime
settings are loaded from `.env`.

## Run bundled examples

The bundled examples are `keysight`, `textron-1`, and `topbuild`. Run
`make examples` to see their numeric aliases and `make help` for the command
summary.

### Full pipeline

The standard targets evaluate by default. The explicit `-eval` alias below has
the same behavior but makes the intent clear.

```bash
# Generate Parts 1, 2, and 3; build the review workbook; evaluate all outputs.
make pipeline-eval EXAMPLE=keysight

# Equivalent standard target: evaluation is enabled by default.
make pipeline EXAMPLE=keysight

# Generate the full pipeline without running the evaluator.
make pipeline EXAMPLE=keysight EVALUATE=0

# Numeric aliases also work: 1=keysight, 2=textron-1, 3=topbuild.
make pipeline EXAMPLE=1 EVALUATE=0
```

### Run each part separately

Run these in order on the first attempt. Part 2 reuses the latest successful
Part 1 bundle, and Part 3 reuses the latest successful upstream bundle required
by `RUBRIC_MAP_PART3_CONTEXT`.

```bash
# Generate and evaluate Part 1.
make part1-eval EXAMPLE=keysight

# Generate Part 2 from the latest Part 1 artifacts and run structural checks.
make part2-eval EXAMPLE=keysight

# Generate and evaluate Part 3 from the latest Part 1/2 lineage.
make part3-eval EXAMPLE=keysight
```

To generate the same stages without evaluation:

```bash
# Part 1 only, without evaluation.
make part1 EXAMPLE=keysight EVALUATE=0

# Part 2 only, using the latest successful Part 1 run.
make part2 EXAMPLE=keysight EVALUATE=0

# Part 3 only, using the context configured in .env.
make part3 EXAMPLE=keysight EVALUATE=0
```

### Run all bundled examples

```bash
# Run and evaluate the complete pipeline for all three examples.
make pipeline-all

# Run the complete pipeline for all three examples without evaluation.
make pipeline-all EVALUATE=0

# Run one stage across all examples. Run these in order on a fresh artifact set.
make part1-all
make part2-all
make part3-all
```

`make pipeline-all` writes the assignment-required `eval_results.json` when
evaluation is enabled. It reports Part 1 and Part 3 precision, recall, and F1
for every labeled example, together with per-part/per-example and overall
runtime and estimated cost. The other `*-all` commands write timestamped batch
evaluation reports under `artifacts/evaluations/`.

## Run another task directory

A task directory needs this layout:

```text
task/
├── input.xlsx
├── complete.xlsx
├── instructions.md
├── rubric.json          # required for Part 3 and the full pipeline
├── sections.json        # gold Part 1 artifact; required only for evaluation
└── items_to_cells.json  # gold Part 3 artifact; required only for evaluation
```

Generate without evaluation when the directory has no gold artifacts:

```bash
# Run the full pipeline.
make run DIR=/absolute/path/to/task STAGE=pipeline EVALUATE=0

# Or run each part separately. Run Part 1 before Part 2, then Part 3.
make run DIR=/absolute/path/to/task STAGE=part1 EVALUATE=0
make run DIR=/absolute/path/to/task STAGE=part2 EVALUATE=0
make run DIR=/absolute/path/to/task STAGE=part3 EVALUATE=0
```

If the task directory contains the matching gold artifacts, enable evaluation:

```bash
# Generate and evaluate the full pipeline.
make run DIR=/absolute/path/to/task STAGE=pipeline EVALUATE=1

# Evaluate individual stages. Part 2 reports structural diagnostics because it
# has no gold artifact.
make run DIR=/absolute/path/to/task STAGE=part1 EVALUATE=1
make run DIR=/absolute/path/to/task STAGE=part2 EVALUATE=1
make run DIR=/absolute/path/to/task STAGE=part3 EVALUATE=1
```

## Dry runs and output location

A dry run resolves inputs, configuration, and upstream lineage without making
model calls or publishing a run. Evaluation must be disabled.

```bash
# Preview a bundled full-pipeline run.
make pipeline EXAMPLE=keysight EVALUATE=0 DRY_RUN=1

# Preview a task-directory run.
make run DIR=/absolute/path/to/task STAGE=pipeline EVALUATE=0 DRY_RUN=1

# Store generated runs under a different artifact root.
make pipeline EXAMPLE=keysight ARTIFACTS_ROOT=/absolute/path/to/artifacts
```

Successful managed runs are written to
`artifacts/example-runs/<task>/<UTC-run-id>/`. A full run contains:

```text
part1/sections.json
part1/summary.md
part1/runtime.json
part1/evaluation.json          # when evaluation is enabled
part2/subsections.json
part2/subsection_index.json
part2/runtime.json
part2/evaluation.json          # structural diagnostics when enabled
part3/items_to_cells.json
part3/runtime.json
part3/evaluation.json          # when evaluation is enabled
review/complete_annotated.xlsx
evaluation.json                # whole-command metrics, cost, and timing
manifest.json
```

The top-level run `evaluation.json` is written even when `EVALUATE=0`; in that
case it contains runtime/cost data and null evaluation entries. For a pipeline
run it contains each part separately and a command total. The reported command
wall time covers generation, deterministic validation, review-workbook
creation, evaluation when enabled, and manifest/report publication. Each
part's process time is also reported separately.

Cost is an estimate in USD, not an invoice. It is calculated from usage
metadata for every model call (uncached input, cached input, cache writes, and
output, including the published long-context multipliers) plus every hosted
Code Interpreter container session. The report embeds the pricing date, rates,
method, and limitations. If usage or a model rate is unavailable, the affected
cost and aggregate total are `null` and `cost_complete` is `false`; missing
usage is never treated as free.

`part2/subsection_index.json` is advisory retrieval context and is not a hard
completion gate. The host preserves agent-authored family and relationship
entries without validating their schema, lineage, or changed-cell coverage. If
either root collection is missing or is not a list, it is replaced with an
empty list so a valid `subsections.json` can continue to Part 3. Part 2
subsections remain strictly validated because evaluation, review generation,
and downstream worksheet lineage depend on them.

## Local tests

```bash
# Run local unit tests. These do not make model calls.
uv run python -m unittest discover -s tests -v
```

## Controlled scope and visual sweep (2026-08-19)

This development-set sweep ran five configurations across Keysight, Textron-1,
and TopBuild: 15 successful runs in total. Sheet stages used
`RUBRIC_MAP_SHEET_MAX_WORKERS=5` throughout, with 4/3/4 actual workers for the
three workbooks. The model was `openai:gpt-5.6-sol` with 4 GB hosted Code
Interpreter containers.

**Best observed setup:** Parts 1 and 2 on sheets, Part 3 on the workbook, and
the visual tool off. It achieved 100.00% / 82.69% / 89.59% Part 1
precision/recall/F1 and 99.19% / 86.83% / 90.71% Part 3 criterion
precision/recall/F1. This was the highest Part 3 F1 in the sweep, which is the
primary quality metric. It processed all three workbooks in 27m 29s for
$11.6516, averaging 9m 10s and $3.8839 per workbook. The tradeoff is cost: it
was about 96% more expensive than running every part at workbook scope with the
visual tool off.

### Aggregate results

Part 1 and Part 3 report task-macro precision/recall/F1. Time and cost are
summed over the three workbooks in each setup.

| Setup | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Total runtime for 3 workbooks | Total estimated cost (model + containers) |
| --- | ---: | ---: | ---: | ---: |
| Parts 1-3 on workbook; visual tool off | 99.57% / 83.32% / 89.91% | 98.74% / 85.82% / 89.84% | 30m 52s | $5.9583 |
| Part 1 on sheets; Parts 2-3 on workbook; visual tool off | 96.15% / 79.11% / 86.47% | 99.50% / 85.15% / 89.66% | 30m 13s | $8.6750 |
| **Parts 1-2 on sheets; Part 3 on workbook; visual tool off (best)** | **100.00% / 82.69% / 89.59%** | **99.19% / 86.83% / 90.71%** | **27m 29s** | **$11.6516** |
| Parts 1-3 on sheets; visual tool off | 100.00% / 83.66% / 90.11% | 99.25% / 85.54% / 89.89% | 24m 41s | $13.3226 |
| Parts 1-3 on workbook; visual tool on | 99.44% / 80.81% / 88.22% | 99.39% / 86.40% / 90.52% | 31m 51s | $7.3563 |

### Average time and cost per workbook

Each cell is `average wall time / average cost` across the three workbooks.
The end-to-end figure also includes validation, evaluation, review-workbook
generation, and artifact publication, so it is slightly larger than the sum of
the three stage process times.

| Setup | Part 1 average time / cost | Part 2 average time / cost | Part 3 average time / cost | Full pipeline average time / cost |
| --- | ---: | ---: | ---: | ---: |
| Parts 1-3 on workbook; visual tool off | 2m 02s / $0.4804 | 5m 04s / $0.8892 | 3m 09s / $0.6165 | 10m 17s / $1.9861 |
| Part 1 on sheets; Parts 2-3 on workbook; visual tool off | 1m 44s / $1.1895 | 5m 09s / $0.9814 | 3m 09s / $0.7208 | 10m 04s / $2.8917 |
| **Parts 1-2 on sheets; Part 3 on workbook; visual tool off (best)** | **1m 57s / $1.1231** | **4m 27s / $2.1252** | **2m 44s / $0.6356** | **9m 10s / $3.8839** |
| Parts 1-3 on sheets; visual tool off | 1m 31s / $1.0970 | 4m 09s / $1.9778 | 2m 30s / $1.3661 | 8m 14s / $4.4409 |
| Parts 1-3 on workbook; visual tool on | 2m 47s / $0.6866 | 5m 11s / $1.0756 | 2m 37s / $0.6900 | 10m 37s / $2.4521 |

[Example-level results for every setup](docs/scope-visual-sweep-example-results.md)
provide the three workbook scores and their Part 1, Part 2, Part 3, and full
pipeline time/cost breakdowns.

Every reported cost includes both model-token charges and hosted Code
Interpreter container charges. The estimates use the official [GPT-5.6 Sol
rates](https://developers.openai.com/api/docs/models/gpt-5.6-sol) and [OpenAI
API/container pricing](https://developers.openai.com/api/docs/pricing); they are
not invoices and exclude LangSmith charges and account-specific adjustments.

The 15 successful runs cost an estimated $46.9639. Known experiment spend was
$49.3480 after adding the priced components from one failed Keysight visual
attempt; that failed attempt's Part 3 cost is incomplete because the provider
returned an HTTP 400 before normal completion.

The workbook-only visual setup reached 90.52% Part 3 F1 with 24 actual captures.
No sheet-level visual run was added because the quality improvement was not
general enough to justify parallel local LibreOffice risk. Running every part
at workbook scope with the visual tool off remains the lower-cost default
pending repeated runs.

This is one stochastic development-set run per task/configuration, not held-out
evidence. Full local artifacts remain under
`artifacts/experiments/scope-visual-model-matrix-20260818T202829.264699Z/` and
are intentionally gitignored.

## Documentation

- [Design notes](DESIGN_NOTES.md): design process, experiments, trade-offs, and
  next steps
- [Prompt history](docs/prompt-history/): chronological Part 1-3 prompt changes
