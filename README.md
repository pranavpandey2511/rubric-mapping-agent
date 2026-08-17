# Rubric Mapping Agent

An isolated, three-stage agent workflow for spreadsheet sectioning and rubric item-to-cell mapping.

The workflow creates overall sections, derives rubric-independent subsections, and then maps rubric items to changed workbook cells. Each stage uses a fresh OpenAI Code Interpreter container and validates its JSON artifact before writing it.

## Repository layout

```text
.
├── src/rubric_mapping_agent/   # Application package and public Python API
├── tests/                      # Local unit tests; no API calls
├── scripts/                    # Evaluation and development utilities
├── skills/xlsx-rubric-mapping/ # Runtime workbook-analysis instructions
├── examples/                   # Labeled sectioning and item-mapping datasets
├── docs/                       # Design record and original assignment
├── evaluator/                  # Exact upstream deterministic evaluator snapshot
├── langgraph.json              # LangGraph development-server graph
└── pyproject.toml              # Package, dependencies, and CLI configuration
```

Generated predictions and evaluation reports belong under `artifacts/`, which is intentionally ignored by Git.

`evaluator/` is an unmodified snapshot of [Theta Software's rubric-mapping evaluator](https://github.com/Theta-Software-Inc/rubric-mapping-eval) at commit `63cf2725ae9b348b834f6be8e1197d3b4ee89b93`. Only the clone's internal `.git` metadata was removed; its upstream files are unchanged.

## Setup

```bash
cp .env.example .env
# Add OPENAI_API_KEY to .env
uv sync --locked
```

`OPENAI_MODEL` defaults to `openai:gpt-5.6-terra`. `OPENAI_CODE_INTERPRETER_MEMORY` defaults to `4g`; larger tiers cost more.

## Run the complete workflow

```bash
uv run rubric-map all \
  --input examples/item-to-cell-mapping/keysight/input.xlsx \
  --complete examples/item-to-cell-mapping/keysight/complete.xlsx \
  --instructions examples/item-to-cell-mapping/keysight/instructions.md \
  --rubric examples/item-to-cell-mapping/keysight/rubric.json \
  --output-dir artifacts/predictions/keysight
```

This produces `sections.json`, `subsections.json`, and `items_to_cells.json`. The rubric is unavailable to the first two stage invocations.

## Run individual stages

```bash
uv run rubric-map part1 \
  --input examples/sectioning/keysight/input.xlsx \
  --complete examples/sectioning/keysight/complete.xlsx \
  --instructions examples/sectioning/keysight/instructions.md \
  --output artifacts/predictions/keysight/sections.json

uv run rubric-map part2 \
  --input examples/sectioning/keysight/input.xlsx \
  --complete examples/sectioning/keysight/complete.xlsx \
  --instructions examples/sectioning/keysight/instructions.md \
  --sections artifacts/predictions/keysight/sections.json \
  --output artifacts/predictions/keysight/subsections.json

uv run rubric-map part3 \
  --input examples/item-to-cell-mapping/keysight/input.xlsx \
  --complete examples/item-to-cell-mapping/keysight/complete.xlsx \
  --instructions examples/item-to-cell-mapping/keysight/instructions.md \
  --rubric examples/item-to-cell-mapping/keysight/rubric.json \
  --sections artifacts/predictions/keysight/sections.json \
  --subsections artifacts/predictions/keysight/subsections.json \
  --output artifacts/predictions/keysight/items_to_cells.json
```

The assignment requires the Part 1 and Part 3 public functions. This project also exposes `create_intermediate_sections(...)` as a rubric-free Part 2 handoff.

## Evaluate and test

Evaluate predictions against all labeled examples:

```bash
uv run python scripts/evaluate_examples.py
```

Run the local tests without making model or Code Interpreter calls:

```bash
uv run python -m unittest discover -s tests -v
```

Run the LangGraph development server:

```bash
uv run langgraph dev --no-browser
```

Running a workflow stage makes OpenAI API calls and incurs model plus Code Interpreter usage. See [docs/DESIGN.md](docs/DESIGN.md) for architecture decisions, implementation status, and known limitations.
