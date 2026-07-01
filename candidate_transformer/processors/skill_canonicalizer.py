"""Skill Canonicalizer Processor.

Maps extracted skill names to canonical versions based on a dictionary
of aliases (e.g., "react.js" -> "React", "node" -> "Node.js").
"""

import json
from pathlib import Path
from typing import Any

from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext


class SkillCanonicalizer(BaseProcessor):
    """Canonicalizes skill names in Evidence records.

    Loads a mapping of alias -> canonical_name from `resources/skill_aliases.json`.
    """

    def __init__(self, aliases_path: Path | None = None) -> None:
        self._aliases: dict[str, str] = {}
        self._aliases_path = aliases_path
        self._loaded = False

    @property
    def name(self) -> str:
        return "SkillCanonicalizer"

    @property
    def order(self) -> int:
        return 20  # Runs after normalizer

    def _load_aliases(self, ctx: PipelineContext) -> None:
        """Load aliases from JSON if available."""
        if self._loaded:
            return

        path = self._aliases_path
        if not path:
            # Default lookup relative to project root
            # candidate_transformer is usually 2 levels down from root
            base_dir = Path(__file__).resolve().parent.parent.parent
            path = base_dir / "resources" / "skill_aliases.json"

        if path.exists():
            try:
                raw_aliases = json.loads(path.read_text(encoding="utf-8"))
                # Store all aliases in lowercase for case-insensitive matching
                self._aliases = {
                    k.strip().lower(): str(v).strip()
                    for k, v in raw_aliases.items()
                }
            except Exception as e:
                ctx.add_warning(f"Failed to parse skill aliases from {path}: {e}")
        else:
            ctx.logger.debug("Skill aliases file not found at %s. Proceeding without aliases.", path)

        self._loaded = True

    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        """Apply alias mapping to all 'skills' Evidence."""
        self._load_aliases(ctx)

        for ev in repo.get_all():
            if ev.field_name == "skills":
                ev.normalized_value = self._canonicalize_skills(
                    ev.normalized_value or ev.raw_value
                )

    def _canonicalize_skills(self, value: Any) -> list[dict[str, Any]]:
        """Canonicalize names in a list of skill dicts."""
        if not isinstance(value, list):
            return value

        canonicalized_skills = []
        for skill_dict in value:
            if not isinstance(skill_dict, dict) or "name" not in skill_dict:
                canonicalized_skills.append(skill_dict)
                continue

            raw_name = str(skill_dict["name"]).strip()
            lookup_name = raw_name.lower()

            canonical_name = self._aliases.get(lookup_name, raw_name)

            # Rebuild dictionary with canonicalized name
            new_skill = dict(skill_dict)
            new_skill["name"] = canonical_name
            canonicalized_skills.append(new_skill)

        # We may have duplicates after canonicalization (e.g. someone listed both 'Node' and 'Node.js').
        # Deduplication happens during the Merging phase, so we return them as-is here.
        return canonicalized_skills
