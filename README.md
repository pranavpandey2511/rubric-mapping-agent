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

## Controlled scope and visual sweep (2026-08-19)

This paid development-set sweep tested the execution-scope ladder requested for
all three bundled workbooks. All 15 planned cells completed successfully. One
Keysight visual run received an OpenAI HTTP 400 during Part 3; the immutable
resume reran that complete cell as attempt 2 and succeeded. The failed attempt
is retained separately and included in the operational-spend accounting below.

The strongest observed Part 3 result was **sheet/sheet/workbook, visual off** at
90.71% task-macro criterion F1. It was 0.87 percentage points above the
all-workbook visual-off baseline, finished 10.96% faster, and cost 95.55% more.
The improvement was not consistent across every workbook or stage, so this
single-run sweep does not support changing the default or running the omitted
local sheet-level visual condition yet.

### Plan, controls, and provenance

`W` means one workbook-scoped agent invocation. `S` means one invocation per
target sheet, executed concurrently inside that stage. Outer workbook runs and
pipeline stages remained sequential.

| Order | Configuration | Visual backend | Runs |
| ---: | --- | --- | ---: |
| 1 | W/W/W | `off` | 3 |
| 2 | S/W/W | `off` | 3 |
| 3 | S/S/W | `off` | 3 |
| 4 | S/S/S | `off` | 3 |
| 5 | W/W/W | `libreoffice_pdf` | 3 |

The experiment ID is
`scope-visual-model-matrix-20260818T202829.264699Z`. It ran from
2026-08-18 20:28:29 UTC to 23:04:58 UTC (2026-08-19 01:58:29 to 04:34:58
IST). Its matrix signature is
`beebb432a0096ac76ae9e97cc19e38f6a585a9a3832170cc147041f4fe0c4a2b`.
The frozen 54-file source snapshot is
`4f078a11f8a32df420f52e9f39a796203651e86ec4b710a00c0a7f6ebe9f78af`,
based on Git commit `38c9c0c32fe71b29d58acbc5e867ae78e155df12` plus the recorded dirty
worktree changes. `plan.json` contains SHA-256 hashes for every input workbook,
completed workbook, instruction file, rubric, and gold artifact.

Fixed controls were:

- model `openai:gpt-5.6-sol`, temperature 0.1, and 4 GB hosted Code
  Interpreter containers;
- Part 3 context `part1_part2`, with both JSON and Markdown handoffs enabled;
- `RUBRIC_MAP_SHEET_MAX_WORKERS=5` for every run, unchanged throughout;
- visual viewport 1440 x 900, 0.6-second capture delay, and 45-second timeout;
- generation followed by deterministic evaluation, using the same three input
  and gold bundles in every configuration; and
- user-approved workbook uploads to OpenAI and LangSmith. LangSmith tracing was
  enabled against project `theta_work_trial`; local artifacts do not contain a
  remote trace receipt, so trace-ingestion completeness is not asserted here.

Keysight and TopBuild each had four target sheets, so sheet-scoped stages used
four workers. Textron-1 had three target sheets and used three workers. The
configured cap remained five in every cell. The visual runs were workbook-only
and sequential, so at most one local LibreOffice-backed inspection context was
active at a time.

Before the paid sweep, 111 application tests passed with 2 skipped, 12 evaluator
tests passed, compilation and whitespace checks passed, and the exact 15-cell
dry run reproduced the matrix signature above. Run 1 (W/W/W off, Keysight) was
the paid smoke test and then became the first completed cell of the resumed
sweep.

### Aggregate results

Part 1 is task-macro section-pair precision/recall/F1. The primary Part 3 score
is task-macro criterion precision/recall/F1; item-macro and pooled micro F1 are
also shown. Part 2 has no gold semantic labels, so its coverage is a structural
diagnostic rather than precision, recall, or accuracy.

| Configuration | P1 P/R/F1 | P2 coverage | P3 criterion P/R/F1 | P3 item F1 | P3 micro F1 | Calls | Tokens | Cost | Captures | Sum of run time |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| W/W/W off | 99.57/83.32/89.91% | 99.97% | 98.74/85.82/89.84% | 89.69% | 88.38% | 27 | 728,127 | $5.9583 | 0 | 30m 52s |
| S/W/W off | 96.15/79.11/86.47% | 99.97% | 99.50/85.15/89.66% | 89.59% | 88.31% | 51 | 1,163,651 | $8.6750 | 0 | 30m 13s |
| S/S/W off | 100.00/82.69/89.59% | 99.97% | 99.19/86.83/90.71% | 90.52% | 89.85% | 75 | 1,487,375 | $11.6516 | 0 | 27m 29s |
| S/S/S off | 100.00/83.66/90.11% | 99.97% | 99.25/85.54/89.89% | 89.90% | 89.07% | 99 | 1,842,698 | $13.3226 | 0 | 24m 41s |
| W/W/W visual | 99.44/80.81/88.22% | 99.97% | 99.39/86.40/90.52% | 90.41% | 89.59% | 38 | 1,032,200 | $7.3563 | 24 | 31m 51s |

Relative to W/W/W off:

| Configuration | P1 F1 delta | P3 criterion F1 delta | Time delta | Cost delta | Token delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| S/W/W off | -3.44 pp | -0.17 pp | -2.12% | +45.59% | +59.81% |
| S/S/W off | -0.32 pp | +0.87 pp | -10.96% | +95.55% | +104.27% |
| S/S/S off | +0.20 pp | +0.05 pp | -20.04% | +123.60% | +153.07% |
| W/W/W visual | -1.69 pp | +0.68 pp | +3.21% | +23.46% | +41.76% |

Sheet-level execution reduced wall time by overlapping hosted invocations, but
it increased calls, containers, tokens, and cost. S/S/W produced the best Part
3 aggregate, driven mainly by Keysight: versus W/W/W off, its per-workbook Part
3 F1 changed by +2.59 pp for Keysight, -0.30 pp for Textron-1, and +0.31 pp for
TopBuild. S/S/S was fastest, but its aggregate Part 3 gain was only 0.05 pp for
123.60% more cost. The evidence is therefore mixed rather than a general
sheet-scope quality improvement.

The visual workbook condition made 24 real captures: 14 in Part 1, 8 in Part 2,
and 2 in Part 3. Compared with W/W/W off, visual access improved aggregate Part
3 criterion F1 by 0.68 pp and micro F1 by 1.21 pp, while reducing Part 1 F1 by
1.69 pp and adding 23.46% cost. Its Part 3 changes were +2.18 pp for Keysight,
-0.30 pp for Textron-1, and +0.17 pp for TopBuild. That is promising for
ambiguous Part 3 cases, but not yet a stable across-task win.

### Per-workbook scores and resources

Every row below is the selected successful attempt. `Captures` counts saved
visual inspections, not merely tool availability. Time is whole-command wall
time, including generation, deterministic validation, review-workbook creation,
evaluation, and artifact publication.

| # | Configuration | Task | P1 P/R/F1 | P2 coverage | P3 criterion P/R/F1 | P3 item F1 | P3 micro F1 | Captures | Calls | Tokens | Cost | Time |
| ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | W/W/W off | Keysight | 100.00/90.93/95.25% | 99.92% | 96.36/87.72/90.02% | 90.26% | 90.78% | 0 | 9 | 250,857 | $2.2005 | 11.90m |
| 2 | W/W/W off | Textron-1 | 98.99/61.48/75.85% | 100.00% | 100.00/75.36/83.34% | 83.06% | 77.87% | 0 | 9 | 205,416 | $1.6546 | 9.20m |
| 3 | W/W/W off | TopBuild | 99.72/97.55/98.62% | 100.00% | 99.87/94.39/96.15% | 95.76% | 95.16% | 0 | 9 | 271,854 | $2.1032 | 9.77m |
| 4 | S/W/W off | Keysight | 100.00/85.63/92.26% | 99.92% | 98.78/85.60/89.60% | 90.28% | 91.26% | 0 | 18 | 418,993 | $3.1972 | 11.45m |
| 5 | S/W/W off | Textron-1 | 88.46/59.89/71.43% | 100.00% | 99.85/74.88/82.89% | 82.55% | 76.55% | 0 | 15 | 339,192 | $2.4131 | 8.44m |
| 6 | S/W/W off | TopBuild | 100.00/91.82/95.73% | 100.00% | 99.87/94.98/96.49% | 95.93% | 95.41% | 0 | 18 | 405,466 | $3.0647 | 10.32m |
| 7 | S/S/W off | Keysight | 100.00/91.73/95.69% | 99.92% | 97.69/90.57/92.61% | 92.79% | 93.59% | 0 | 27 | 530,326 | $4.4045 | 10.48m |
| 8 | S/S/W off | Textron-1 | 100.00/59.76/74.81% | 100.00% | 100.00/75.03/83.04% | 82.76% | 77.56% | 0 | 21 | 381,785 | $2.7468 | 7.90m |
| 9 | S/S/W off | TopBuild | 100.00/96.58/98.26% | 100.00% | 99.87/94.91/96.46% | 96.02% | 95.61% | 0 | 27 | 575,264 | $4.5003 | 9.10m |
| 10 | S/S/S off | Keysight | 100.00/94.13/96.97% | 99.92% | 98.32/86.70/90.35% | 91.06% | 92.43% | 0 | 36 | 713,578 | $5.3665 | 9.42m |
| 11 | S/S/S off | Textron-1 | 100.00/59.88/74.91% | 100.00% | 100.00/75.36/83.34% | 83.06% | 77.87% | 0 | 27 | 442,397 | $2.9630 | 6.77m |
| 12 | S/S/S off | TopBuild | 100.00/96.97/98.46% | 100.00% | 99.44/94.57/95.98% | 95.59% | 94.60% | 0 | 36 | 686,723 | $4.9932 | 8.49m |
| 13 | W/W/W visual | Keysight | 100.00/84.58/91.65% | 99.92% | 98.30/89.54/92.20% | 92.54% | 93.28% | 7 | 12 | 362,804 | $2.6729 | 11.37m |
| 14 | W/W/W visual | Textron-1 | 100.00/59.76/74.81% | 100.00% | 100.00/75.03/83.04% | 82.76% | 77.56% | 7 | 12 | 271,531 | $1.9308 | 9.07m |
| 15 | W/W/W visual | TopBuild | 98.31/98.09/98.20% | 100.00% | 99.87/94.65/96.32% | 95.94% | 95.26% | 10 | 14 | 397,865 | $2.7526 | 11.42m |

### Stage-level time, cost, tokens, and calls

Each stage entry is `process seconds / estimated USD / tokens / model calls`.
For sheet scope, process time is elapsed wall time for the concurrent stage, not
the sum of its individual worker durations.

| # | Configuration/task | Part 1 | Part 2 | Part 3 | Command total |
| ---: | --- | ---: | ---: | ---: | ---: |
| 1 | W/W/W off / Keysight | 149.81s / $0.5774 / 80,872 / 3 | 323.30s / $0.9475 / 95,655 / 3 | 238.97s / $0.6756 / 74,330 / 3 | 713.80s / $2.2005 |
| 2 | W/W/W off / Textron-1 | 101.00s / $0.3767 / 59,618 / 3 | 286.89s / $0.7864 / 81,538 / 3 | 161.66s / $0.4914 / 64,260 / 3 | 551.75s / $1.6546 |
| 3 | W/W/W off / TopBuild | 114.05s / $0.4871 / 72,237 / 3 | 302.03s / $0.9336 / 103,800 / 3 | 167.53s / $0.6825 / 95,817 / 3 | 586.20s / $2.1032 |
| 4 | S/W/W off / Keysight | 91.93s / $1.2697 / 200,972 / 12 | 363.32s / $1.0935 / 114,856 / 3 | 229.72s / $0.8340 / 103,165 / 3 | 686.78s / $3.1972 |
| 5 | S/W/W off / Textron-1 | 99.52s / $1.0199 / 173,251 / 9 | 269.85s / $0.8407 / 86,778 / 3 | 134.45s / $0.5525 / 79,163 / 3 | 506.37s / $2.4131 |
| 6 | S/W/W off / TopBuild | 121.03s / $1.2788 / 194,613 / 12 | 292.40s / $1.0101 / 106,259 / 3 | 203.37s / $0.7758 / 104,594 / 3 | 619.43s / $3.0647 |
| 7 | S/S/W off / Keysight | 124.56s / $1.2528 / 183,856 / 12 | 312.86s / $2.4258 / 252,645 / 12 | 189.29s / $0.7259 / 93,825 / 3 | 628.58s / $4.4045 |
| 8 | S/S/W off / Textron-1 | 113.60s / $0.7540 / 124,960 / 9 | 224.96s / $1.4223 / 173,566 / 9 | 133.21s / $0.5705 / 83,259 / 3 | 474.20s / $2.7468 |
| 9 | S/S/W off / TopBuild | 112.29s / $1.3624 / 210,964 / 12 | 261.72s / $2.5274 / 283,665 / 12 | 169.38s / $0.6105 / 80,635 / 3 | 546.00s / $4.5003 |
| 10 | S/S/S off / Keysight | 94.50s / $1.1818 / 192,099 / 12 | 313.46s / $2.5086 / 276,443 / 12 | 155.13s / $1.6761 / 245,036 / 12 | 564.97s / $5.3665 |
| 11 | S/S/S off / Textron-1 | 79.44s / $0.6809 / 113,272 / 9 | 190.76s / $1.2469 / 165,699 / 9 | 133.38s / $1.0353 / 163,426 / 9 | 406.09s / $2.9630 |
| 12 | S/S/S off / TopBuild | 100.45s / $1.4282 / 235,756 / 12 | 244.07s / $2.1781 / 245,791 / 12 | 162.63s / $1.3868 / 205,176 / 12 | 509.58s / $4.9932 |
| 13 | W/W/W visual / Keysight | 176.95s / $0.7389 / 114,288 / 4 | 294.74s / $1.0862 / 131,371 / 4 | 208.88s / $0.8478 / 117,145 / 4 | 682.22s / $2.6729 |
| 14 | W/W/W visual / Textron-1 | 171.06s / $0.5305 / 92,487 / 5 | 276.47s / $0.9380 / 109,167 / 4 | 94.05s / $0.4623 / 69,877 / 3 | 544.00s / $1.9308 |
| 15 | W/W/W visual / TopBuild | 152.49s / $0.7903 / 150,077 / 6 | 360.72s / $1.2025 / 141,010 / 4 | 169.26s / $0.7598 / 106,778 / 4 | 685.04s / $2.7526 |

### Cost, retry, artifacts, and decision

The 15 selected successful runs used 6,254,051 tokens, 290 model calls, 93
hosted container sessions, and 2h 25m 05s of summed command time. Their
estimated cost was $46.9639: $44.1379 for model usage and $2.8260 for hosted
containers. The experiment's end-to-end elapsed time, including smoke/resume
overhead and the failed attempt, was 2h 36m 29s.

Keysight W/W/W visual attempt 1 completed Part 1 and Part 2, then received an
OpenAI `invalid_request_error` HTTP 400 in Part 3 without a specific parameter.
Its recorded stages consumed 321,643 tokens, 11 model calls, and 3 container
sessions over 632.35 stage-seconds. The known priced components were $2.3841:
$0.7468 for Part 1, $1.1520 for Part 2, and $0.4853 for the calls and container
recorded before Part 3 failed. Part 3 correctly marked `cost_complete=false`,
so this is a known-component estimate, not a complete failed-attempt total.
Adding those known components to successful-run cost gives known experiment
spend of $49.3480.

Costs are estimates, not invoices. They use recorded uncached input, cached
input, cache-write, and output tokens plus per-session container time, applying
the published long-context multipliers where applicable. The embedded pricing
snapshot is dated 2026-08-19. See the official [GPT-5.6 Sol model
rates](https://developers.openai.com/api/docs/models/gpt-5.6-sol) and [OpenAI
API pricing](https://developers.openai.com/api/docs/pricing). Account-specific
credits, negotiated rates, data-residency uplifts, LangSmith charges, and usage
not returned by an interrupted request are excluded.

The full local evidence is under
`artifacts/experiments/scope-visual-model-matrix-20260818T202829.264699Z/`:

- `plan.json` records the immutable matrix, environment, hashes, and
  provenance;
- `results.json` records all selected runs, scores, runtime telemetry, and
  aggregates;
- `summary.md` is the generated compact report; and
- each successful run contains its manifest, top-level evaluation, three stage
  evaluations and runtimes, model outputs, review workbook, and any visual
  captures.

The `artifacts/` tree is intentionally gitignored, so these paid-run files stay
local and are not pushed. This README is the committed result record.

No sheet-level visual cell was run. Concurrent local `libreoffice_pdf`
inspection could create several LibreOffice processes, exceed local memory, and
destabilize the run. The agreed trigger was a general sheet-scope quality win;
this sweep instead showed a mixed, task-dependent result at substantially
higher cost. If that condition changes after repeated runs, test sheet-level
visuals as a separately controlled, serialized or capacity-limited experiment.
Until then, retain W/W/W off as the conservative default and treat S/S/W off
and W/W/W visual as promising follow-up candidates rather than defaults.

Interpretation limits:

- each cell is one stochastic development-set run, with no repeats or
  confidence intervals;
- the same three workbooks were used for development and comparison, so these
  are not held-out generalization results;
- Part 2 coverage verifies changed-cell inclusion, not semantic subsection
  correctness;
- screenshots support layout interpretation but do not override exact cell,
  formula, diff, or rubric evidence; and
- small score differences may be sampling noise and need controlled reruns
  before a production policy change.

## Documentation

- [Design notes](DESIGN_NOTES.md): design process, experiments, trade-offs, and
  next steps
- [Prompt history](docs/prompt-history/): chronological Part 1-3 prompt changes
