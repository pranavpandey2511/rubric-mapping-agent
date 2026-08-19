# Example-level scope and visual sweep results

These are the selected successful runs from experiment
`scope-visual-model-matrix-20260818T202829.264699Z`. All runs used
`openai:gpt-5.6-sol` and 4 GB hosted Code Interpreter containers. Costs include
both model-token and container charges. Stage time is process wall time; full
pipeline time also includes validation, evaluation, review-workbook generation,
and artifact publication.

Scores are shown as precision / recall / F1. The primary quality metric is Part
3 task-macro criterion F1.

## Parts 1-3 on workbook; visual tool off

| Example | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Part 1 time / cost | Part 2 time / cost | Part 3 time / cost | Full pipeline time / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keysight | 100.00% / 90.93% / 95.25% | 96.36% / 87.72% / 90.02% | 2m 30s / $0.5774 | 5m 23s / $0.9475 | 3m 59s / $0.6756 | 11m 54s / $2.2005 |
| Textron-1 | 98.99% / 61.48% / 75.85% | 100.00% / 75.36% / 83.34% | 1m 41s / $0.3767 | 4m 47s / $0.7864 | 2m 42s / $0.4914 | 9m 12s / $1.6546 |
| TopBuild | 99.72% / 97.55% / 98.62% | 99.87% / 94.39% / 96.15% | 1m 54s / $0.4871 | 5m 02s / $0.9336 | 2m 48s / $0.6825 | 9m 46s / $2.1032 |

## Part 1 on sheets; Parts 2-3 on workbook; visual tool off

| Example | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Part 1 time / cost | Part 2 time / cost | Part 3 time / cost | Full pipeline time / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keysight | 100.00% / 85.63% / 92.26% | 98.78% / 85.60% / 89.60% | 1m 32s / $1.2697 | 6m 03s / $1.0935 | 3m 50s / $0.8340 | 11m 27s / $3.1972 |
| Textron-1 | 88.46% / 59.89% / 71.43% | 99.85% / 74.88% / 82.89% | 1m 40s / $1.0199 | 4m 30s / $0.8407 | 2m 14s / $0.5525 | 8m 26s / $2.4131 |
| TopBuild | 100.00% / 91.82% / 95.73% | 99.87% / 94.98% / 96.49% | 2m 01s / $1.2788 | 4m 52s / $1.0101 | 3m 23s / $0.7758 | 10m 19s / $3.0647 |

## Parts 1-2 on sheets; Part 3 on workbook; visual tool off

| Example | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Part 1 time / cost | Part 2 time / cost | Part 3 time / cost | Full pipeline time / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keysight | 100.00% / 91.73% / 95.69% | 97.69% / 90.57% / 92.61% | 2m 05s / $1.2528 | 5m 13s / $2.4258 | 3m 09s / $0.7259 | 10m 29s / $4.4045 |
| Textron-1 | 100.00% / 59.76% / 74.81% | 100.00% / 75.03% / 83.04% | 1m 54s / $0.7540 | 3m 45s / $1.4223 | 2m 13s / $0.5705 | 7m 54s / $2.7468 |
| TopBuild | 100.00% / 96.58% / 98.26% | 99.87% / 94.91% / 96.46% | 1m 52s / $1.3624 | 4m 22s / $2.5274 | 2m 49s / $0.6105 | 9m 06s / $4.5003 |

## Parts 1-3 on sheets; visual tool off

| Example | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Part 1 time / cost | Part 2 time / cost | Part 3 time / cost | Full pipeline time / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keysight | 100.00% / 94.13% / 96.97% | 98.32% / 86.70% / 90.35% | 1m 35s / $1.1818 | 5m 13s / $2.5086 | 2m 35s / $1.6761 | 9m 25s / $5.3665 |
| Textron-1 | 100.00% / 59.88% / 74.91% | 100.00% / 75.36% / 83.34% | 1m 19s / $0.6809 | 3m 11s / $1.2469 | 2m 13s / $1.0353 | 6m 46s / $2.9630 |
| TopBuild | 100.00% / 96.97% / 98.46% | 99.44% / 94.57% / 95.98% | 1m 40s / $1.4282 | 4m 04s / $2.1781 | 2m 43s / $1.3868 | 8m 30s / $4.9932 |

## Parts 1-3 on workbook; visual tool on

| Example | Part 1 precision / recall / F1 | Part 3 criterion precision / recall / F1 | Part 1 time / cost | Part 2 time / cost | Part 3 time / cost | Full pipeline time / cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Keysight | 100.00% / 84.58% / 91.65% | 98.30% / 89.54% / 92.20% | 2m 57s / $0.7389 | 4m 55s / $1.0862 | 3m 29s / $0.8478 | 11m 22s / $2.6729 |
| Textron-1 | 100.00% / 59.76% / 74.81% | 100.00% / 75.03% / 83.04% | 2m 51s / $0.5305 | 4m 36s / $0.9380 | 1m 34s / $0.4623 | 9m 04s / $1.9308 |
| TopBuild | 98.31% / 98.09% / 98.20% | 99.87% / 94.65% / 96.32% | 2m 32s / $0.7903 | 6m 01s / $1.2025 | 2m 49s / $0.7598 | 11m 25s / $2.7526 |

[Back to the aggregate sweep summary](../README.md#controlled-scope-and-visual-sweep-2026-08-19).
