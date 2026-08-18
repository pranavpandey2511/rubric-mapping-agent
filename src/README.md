# `src` directory map

`src/` contains the installable `rubric_mapping_agent` package. For the main
pipeline, start with `cli.py` for commands or `workflow.py` for programmatic
orchestration.

```text
src/
├── README.md                         # This navigation map
├── rubric_mapping_agent/
│   ├── __init__.py                   # Lazy public package exports
│   ├── artifacts.py                  # Atomic JSON and text file writers
│   ├── cli.py                        # `rubric-map` command and subcommands
│   ├── configuration.py              # Validated environment settings
│   ├── handoff.py                    # Cross-stage context and summaries
│   ├── managed_runs.py               # Run lineage, manifests, and evaluation
│   ├── retrieval_index.py            # Part 2 semantic-index contract
│   ├── stage_outputs.py              # Stage output validation and merging
│   ├── workflow.py                   # Part 1–3 pipeline orchestration
│   ├── review/                       # Annotated review-workbook creation
│   ├── runtime/                      # Model, skills, and hosted execution
│   └── visual/                       # Read-only workbook screenshots
└── rubric_mapping_agent.egg-info/     # Generated packaging metadata
```

## Top-level package files

- `__init__.py` defines the small public Python API and lazy-loads workflow and
  review functions so optional runtime dependencies are imported only when used.
- `artifacts.py` safely writes JSON and text artifacts through temporary files
  and atomic replacement.
- `cli.py` defines the `part1`, `part2`, `part3`, `all`, and `visualize`
  subcommands and routes them to the workflow or review layer.
- `configuration.py` reads and validates stage scope, Part 3 context, and
  worksheet concurrency environment variables.
- `handoff.py` controls which Part 1/2 artifacts are passed to later stages. It
  also validates, renders, and parses the deterministic Part 1 Markdown summary.
- `managed_runs.py` finds compatible upstream artifacts, reads and writes run
  manifests, and evaluates completed Part 1–3 outputs for managed example runs.
- `retrieval_index.py` validates the Part 2 `subsection_index.json` schema,
  semantic families, changed-cell coverage, lineage, roles, and relationships.
- `stage_outputs.py` validates agent-produced artifacts, computes eligible
  workbook-diff cells, and combines sheet-scoped outputs into workbook outputs.
- `workflow.py` is the main application layer. It runs Parts 1–3, selects sheet
  or workbook scope, parallelizes sheet calls, validates handoffs, and writes the
  final artifacts.

## `runtime/`

- `__init__.py` re-exports the runtime's supported classes and constructors.
- `agent.py` constructs the Deep Agent, selects the OpenAI model, binds it to a
  hosted Code Interpreter container, and defines its structured artifact receipt.
- `skills.py` builds a temporary, stage-specific skill bundle containing only
  the selected Part 1, 2, or 3 instructions and output contract.
- `stage.py` owns one hosted stage call: it creates the network-disabled
  container, uploads allowed inputs, builds the prompt, runs the agent,
  downloads JSON outputs, and cleans up the container and temporary resources.

## `review/`

- `__init__.py` exposes the review-workbook API and shared visualization markers.
- `contracts.py` contains review data models and parsers, adds review-only Part 2
  coverage when needed, and validates that mappings point to valid workbook cells.
- `overlays.py` applies Part 1 outlines, Part 2 period boundaries, and Part 3
  highlights/comments to workbook cells.
- `legend.py` creates the `Mapping Legend` worksheet explaining all overlays.
- `ooxml.py` restores original formulas, values, types, and cached values after
  OpenPyXL changes workbook styles.
- `workbook.py` coordinates parsing, validation, overlays, legend creation,
  source-payload restoration, and final annotated workbook output.

## `visual/`

- `__init__.py` exposes the visual-runtime constructor.
- `inspection.py` implements the agent-facing, read-only workbook screenshot
  tool, viewport navigation, configuration, capture metadata, and LibreOffice
  PDF/UI backends.
- `_libreoffice_bridge.py` is the dependency-light PyUNO helper executed by
  LibreOffice's Python to open workbooks read-only, render or position a range,
  and shut down the isolated LibreOffice process.

## Generated directories

- `rubric_mapping_agent.egg-info/` is produced by package installation:
  `PKG-INFO` contains package metadata and the long description; `SOURCES.txt`
  lists packaged files; `requires.txt` lists dependencies; `entry_points.txt`
  registers `rubric-map`; `dependency_links.txt` stores dependency-link
  metadata; and `top_level.txt` records the import package name. Do not edit
  these files directly; `pyproject.toml` is their source of truth.
- Any `__pycache__/` directory contains generated `.pyc` bytecode for faster
  imports. It is not application source.

## Main execution path

```text
cli.py → workflow.py → runtime/stage.py
                         ├─→ runtime/agent.py + runtime/skills.py
                         ├─→ visual/inspection.py (when enabled)
                         └─→ stage_outputs.py → artifacts.py

cli.py visualize → review/workbook.py → contracts + overlays + legend + ooxml
```
