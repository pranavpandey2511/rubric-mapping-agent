"""Materialize the exact skill files visible to one stage invocation."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SKILLS_ROOT = PROJECT_ROOT / "skills"
STAGE_REFERENCE_DIRS = {
    "part1": "part-1",
    "part2": "part-2",
    "part3": "part-3",
}


@dataclass
class StageSkillBundle:
    """Temporary read-only skill source retained for one agent invocation."""

    root: Path
    stage: str
    visual_enabled: bool
    _temporary: tempfile.TemporaryDirectory

    def close(self) -> None:
        self._temporary.cleanup()


def create_stage_skill_bundle(
    stage: str,
    *,
    visual_enabled: bool,
    skills_root: Path = DEFAULT_SKILLS_ROOT,
) -> StageSkillBundle:
    """Expose one stage and exactly one normal-or-visual workflow variant."""

    try:
        reference_dir_name = STAGE_REFERENCE_DIRS[stage]
    except KeyError as exc:
        raise ValueError(f"Unknown stage {stage!r}") from exc

    skills_root = skills_root.resolve()
    excel_source = skills_root / "excel"
    mapping_source = skills_root / "xlsx-rubric-mapping"
    reference_source = mapping_source / "references" / reference_dir_name
    canonical_workflow_name = f"{reference_dir_name}-workflow.md"
    workflow_source_name = (
        f"{reference_dir_name}-workflow-visual.md"
        if visual_enabled
        else canonical_workflow_name
    )
    required = (
        excel_source / "SKILL.md",
        mapping_source / "SKILL.md",
        reference_source / workflow_source_name,
        reference_source / "output-format.md",
    )
    missing = [path for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing stage skill source(s): " + ", ".join(map(str, missing))
        )

    temporary = tempfile.TemporaryDirectory(prefix=f"rubric-map-{stage}-skills-")
    bundle_root = Path(temporary.name).resolve()
    try:
        shutil.copytree(excel_source, bundle_root / "excel")

        mapping_destination = bundle_root / "xlsx-rubric-mapping"
        mapping_destination.mkdir()
        shutil.copy2(mapping_source / "SKILL.md", mapping_destination / "SKILL.md")

        reference_destination = (
            mapping_destination / "references" / reference_dir_name
        )
        reference_destination.mkdir(parents=True)
        shutil.copy2(
            reference_source / workflow_source_name,
            reference_destination / canonical_workflow_name,
        )
        shutil.copy2(
            reference_source / "output-format.md",
            reference_destination / "output-format.md",
        )
    except Exception:
        temporary.cleanup()
        raise

    return StageSkillBundle(
        root=bundle_root,
        stage=stage,
        visual_enabled=visual_enabled,
        _temporary=temporary,
    )
