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

## Recorded development baseline

This is the complete three-workbook run used as the initial full-pipeline
reference. It is development-set evidence, not a held-out result. Part 2 has no
gold artifact, so only structural coverage is reported.

| Stage | Precision | Recall | F1 | Additional result |
| --- | ---: | ---: | ---: | --- |
| Part 1 | 100.00%* | 84.61% | 90.60% | 79 predicted sections |
| Part 2 | N/A | N/A | N/A | 99.97% diff coverage; 450 subsections; 0 separators |
| Part 3 | 70.20% | 96.43% | 76.49% | 353/353 rubric items mapped |

| Example | Part 1 P/R/F1 | Part 2 diff coverage | Part 3 P/R/F1 | Tokens | Cost | Time |
| --- | --- | --- | --- | ---: | ---: | ---: |
| Keysight | 100.00 / 95.20 / 97.54% | 1,262/1,263 (99.92%) | 97.56 / 93.17 / 94.60% | 351,186 | $2.3792 | 12m 52.5s |
| Textron-1 | 100.00 / 59.88 / 74.91% | 1,337/1,337 (100.00%) | 58.37 / 97.89 / 68.80% | 241,237 | $1.5269 | 7m 24.7s |
| TopBuild | 99.99 / 98.75 / 99.37% | 1,051/1,051 (100.00%) | 54.68 / 98.25 / 66.06% | 372,133 | $2.5427 | 12m 48.0s |

\* Exact Part 1 precision was 99.9958%. A later controlled Part 3 prompt study,
using frozen Part 1/2 artifacts, improved Part 3 task-macro F1 to 89.55%.

## Documentation

- [Design notes](DESIGN_NOTES.md): design process, experiments, trade-offs, and
  next steps
- [Prompt history](docs/prompt-history/): chronological Part 1-3 prompt changes
