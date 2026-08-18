# Rubric-mapping workflow commands
#
# General help and bundled-example aliases:
#   make help
#   make examples
#
# Run any task directory (evaluation is enabled by default):
#   make run DIR=/path/to/task STAGE=part1
#   make run DIR=/path/to/task STAGE=part2
#   make run DIR=/path/to/task STAGE=part3
#   make run DIR=/path/to/task STAGE=pipeline
#
# Run one bundled example by name:
#   make part1 EXAMPLE=keysight
#   make part2 EXAMPLE=keysight
#   make part3 EXAMPLE=keysight
#   make pipeline EXAMPLE=keysight
#
# EXAMPLE also accepts the numeric aliases shown by `make examples`:
#   make pipeline EXAMPLE=1
#
# Run a stage for every bundled example:
#   make part1-all
#   make part2-all
#   make part3-all
#   make pipeline-all
#
# Explicit evaluated aliases for one bundled example:
#   make part1-eval EXAMPLE=keysight
#   make part2-eval EXAMPLE=keysight
#   make part3-eval EXAMPLE=keysight
#   make pipeline-eval EXAMPLE=keysight
#
# Optional controls (these work with `run` and the standard example targets):
#   make run DIR=/path/to/task STAGE=pipeline EVALUATE=0
#   make run DIR=/path/to/task STAGE=pipeline EVALUATE=0 DRY_RUN=1
#   make part1 EXAMPLE=keysight EVALUATE=0
#   make pipeline EXAMPLE=keysight EVALUATE=0 DRY_RUN=1
#   make run DIR=/path/to/task STAGE=pipeline ARTIFACTS_ROOT=/path/to/artifacts
#   make pipeline-all EXAMPLES_ROOT=/path/to/bundled-examples
#
# Runtime configuration is loaded from .env. A dry run must disable evaluation.

# User-selectable inputs and controls.
EXAMPLE ?=
DIR ?=
STAGE ?=
EXAMPLES_ROOT ?= examples/item-to-cell-mapping
ARTIFACTS_ROOT ?= artifacts/example-runs
EVALUATE ?= 1
DRY_RUN ?= 0

# Internal runner command and derived flags.
EXAMPLE_RUNNER := uv run python scripts/run_example.py
EVALUATE_FLAG := $(if $(filter 1 true yes,$(EVALUATE)),--evaluate,)
DRY_RUN_FLAG := $(if $(filter 1 true yes,$(DRY_RUN)),--dry-run,)
AVAILABLE_EXAMPLES := $(sort $(notdir $(patsubst %/,%,$(wildcard $(EXAMPLES_ROOT)/*/))))

.PHONY: help examples require-example require-run-args run part1 part2 part3 pipeline \
	part1-all part2-all part3-all pipeline-all \
	part1-eval part2-eval part3-eval pipeline-eval

# Print the supported commands and common options.
help:
	@echo "Rubric-mapping example runner"
	@echo
	@echo "Run any task directory through one entry point:"
	@echo
	@echo "  make run DIR=/path/to/task STAGE=part1"
	@echo "  make run DIR=/path/to/task STAGE=part2"
	@echo "  make run DIR=/path/to/task STAGE=part3"
	@echo "  make run DIR=/path/to/task STAGE=pipeline"
	@echo
	@echo "  make part1 EXAMPLE=keysight"
	@echo "  make part2 EXAMPLE=keysight"
	@echo "  make part3 EXAMPLE=keysight"
	@echo "  make pipeline EXAMPLE=keysight"
	@echo
	@echo "Run a stage for every example:"
	@echo
	@echo "  make part1-all"
	@echo "  make part2-all"
	@echo "  make part3-all"
	@echo "  make pipeline-all"
	@echo
	@echo "The commands above generate and evaluate by default."
	@echo "Each successful run also writes review/complete_annotated.xlsx."
	@echo
	@echo "Explicit evaluation aliases:"
	@echo
	@echo "  make part1-eval EXAMPLE=keysight"
	@echo "  make part2-eval EXAMPLE=keysight"
	@echo "  make part3-eval EXAMPLE=keysight"
	@echo "  make pipeline-eval EXAMPLE=keysight"
	@echo
	@echo "Skip evaluation: make part1 EXAMPLE=keysight EVALUATE=0"
	@echo
	@echo "EXAMPLE also accepts 1, 2, or 3. Run 'make examples' for the mapping."
	@echo "Runtime settings are loaded from .env."
	@echo "Artifacts default to $(ARTIFACTS_ROOT)."

# Print the numeric aliases accepted by EXAMPLE.
examples:
	@echo "1  keysight"
	@echo "2  textron-1"
	@echo "3  topbuild"

# Validate the shared argument used by the bundled-example targets.
require-example:
	@if [ -z "$(EXAMPLE)" ]; then \
		echo "EXAMPLE is required. Try: make part1 EXAMPLE=keysight" >&2; \
		exit 2; \
	fi

# Validate the directory runner's required arguments and stage name.
require-run-args:
	@if [ -z "$(DIR)" ]; then \
		echo "DIR is required. Try: make run DIR=/path/to/task STAGE=pipeline" >&2; \
		exit 2; \
	fi
	@if [ -z "$(STAGE)" ]; then \
		echo "STAGE is required (part1, part2, part3, or pipeline)." >&2; \
		exit 2; \
	fi
	@case "$(STAGE)" in \
		part1|part2|part3|pipeline) ;; \
		*) echo "STAGE must be part1, part2, part3, or pipeline." >&2; exit 2 ;; \
	esac

# Run one selected stage, or the complete pipeline, for any task directory.
run: require-run-args
	@$(EXAMPLE_RUNNER) "$(STAGE)" --directory "$(DIR)" \
		--artifacts-root "$(ARTIFACTS_ROOT)" $(EVALUATE_FLAG) $(DRY_RUN_FLAG)

# Run one stage or pipeline for a single bundled example.
part1 part2 part3 pipeline: require-example
	@$(EXAMPLE_RUNNER) $@ --example "$(EXAMPLE)" --artifacts-root "$(ARTIFACTS_ROOT)" \
		$(EVALUATE_FLAG) $(DRY_RUN_FLAG)

# Run the selected stage or pipeline for every bundled example.
part1-all part2-all part3-all pipeline-all:
	@set -e; \
	for example in $(AVAILABLE_EXAMPLES); do \
		echo "==> $(patsubst %-all,%,$@): $$example"; \
		$(MAKE) $(patsubst %-all,%,$@) EXAMPLE="$$example"; \
	done

# Explicit evaluation aliases for a single bundled example.
part1-eval part2-eval part3-eval pipeline-eval: require-example
	@$(EXAMPLE_RUNNER) $(patsubst %-eval,%,$@) --example "$(EXAMPLE)" \
		--artifacts-root "$(ARTIFACTS_ROOT)" --evaluate
