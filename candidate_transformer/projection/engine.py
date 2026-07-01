"""Projection Engine layer.

Converts the internal CanonicalCandidate objects into external dictionary shapes
as defined by the OutputConfig and FieldSpecs. Handles path traversal,
selective serialization, confidence omission, and missing value policies.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from candidate_transformer.config.models import OutputConfig, FieldSpec
from candidate_transformer.domain.enums import MissingPolicy
from candidate_transformer.domain.exceptions import ValidationError
from candidate_transformer.domain.models.candidate import CanonicalCandidate, Skill


class ProjectionEngine:
    """Reshapes CanonicalCandidate objects into configuration-specified dictionaries."""

    def __init__(self, aliases_path: Path | None = None) -> None:
        self._aliases: dict[str, str] = {}
        self._aliases_path = aliases_path
        self._loaded = False
        self._logger = logging.getLogger("candidate_transformer.projection.engine")

    def _load_aliases(self) -> None:
        """Load aliases from JSON if available for projection-level normalisation."""
        if self._loaded:
            return

        path = self._aliases_path
        if not path:
            base_dir = Path(__file__).resolve().parent.parent.parent
            path = base_dir / "resources" / "skill_aliases.json"

        if path.exists():
            try:
                raw_aliases = json.loads(path.read_text(encoding="utf-8"))
                self._aliases = {
                    k.strip().lower(): str(v).strip()
                    for k, v in raw_aliases.items()
                }
            except Exception as e:
                self._logger.warning("Failed to parse skill aliases from %s: %s", path, e)
        self._loaded = True

    def project(self, candidate: CanonicalCandidate, config: OutputConfig) -> dict[str, Any]:
        """Project a single CanonicalCandidate into the output dict shape."""
        self._load_aliases()
        output: dict[str, Any] = {}

        # Determine which fields to project
        fields_to_project = config.fields
        is_default_projection = len(fields_to_project) == 0

        if is_default_projection:
            # Reconstruct default FieldSpecs for all attributes of CanonicalCandidate
            # Exclude metadata like overall_confidence and provenance if conditionally toggled
            default_paths = [
                "candidate_id",
                "full_name",
                "emails",
                "phones",
                "location",
                "links",
                "headline",
                "years_experience",
                "skills",
                "experience",
                "education",
                "provenance",
            ]
            if config.include_confidence:
                default_paths.append("overall_confidence")

            fields_to_project = [
                FieldSpec(path=p, resolved_from=p) for p in default_paths
            ]

        for spec in fields_to_project:
            resolved_path = spec.resolved_from or spec.path
            tokens = self._parse_path(resolved_path)
            raw_value = self._get_value(candidate, tokens)

            # Check if missing
            if raw_value is None:
                if spec.required:
                    raise ValidationError(
                        f"Required field '{spec.path}' (from path '{resolved_path}') is missing.",
                        context={"field": spec.path, "path": resolved_path}
                    )
                if config.on_missing == MissingPolicy.ERROR:
                    raise ValidationError(
                        f"Field '{spec.path}' is missing and global policy is 'error'.",
                        context={"field": spec.path, "path": resolved_path}
                    )
                if config.on_missing == MissingPolicy.OMIT:
                    continue
                # NULL policy -> output[spec.path] = None
                output[spec.path] = None
                continue

            # Apply field-specific normalization if requested
            if spec.normalize:
                raw_value = self._apply_normalization(raw_value, spec.normalize)

            # Recursively serialize value and exclude confidence if needed
            serialized = self._serialize_value(raw_value, config.include_confidence)
            output[spec.path] = serialized

        return output

    def project_many(
        self, candidates: list[CanonicalCandidate], config: OutputConfig
    ) -> list[dict[str, Any]]:
        """Project multiple CanonicalCandidates."""
        return [self.project(c, config) for c in candidates]

    def _parse_path(self, path: str) -> list[str | int]:
        """Tokenize dot and bracket notations like 'skills[].name' or 'emails[0]'."""
        tokens: list[str | int] = []
        pattern = re.compile(r'([a-zA-Z_0-9]+)|\[(\d*)\]')
        for match in pattern.finditer(path):
            word, index = match.groups()
            if word:
                tokens.append(word)
            elif index == "":
                tokens.append("[]")
            else:
                tokens.append(int(index))
        return tokens

    def _get_value(self, obj: Any, tokens: list[str | int]) -> Any:
        """Resolve the value along the tokenized path."""
        current = obj
        for i, token in enumerate(tokens):
            if current is None:
                return None

            if token == "[]":
                if not isinstance(current, list):
                    return None
                remaining = tokens[i + 1 :]
                # Map get_value recursively over the list
                return [self._get_value(item, remaining) for item in current]

            if isinstance(token, int):
                if not isinstance(current, list):
                    return None
                try:
                    current = current[token]
                except IndexError:
                    return None
            else:
                if hasattr(current, token):
                    current = getattr(current, token)
                elif isinstance(current, dict):
                    current = current.get(token)
                else:
                    return None
        return current

    def _apply_normalization(self, val: Any, mode: str) -> Any:
        """Apply phone E164 formatting or skill canonicalization."""
        if mode == "E164":
            if isinstance(val, list):
                return [self._normalize_phone(p) for p in val if p]
            return self._normalize_phone(val)
        elif mode == "canonical":
            if isinstance(val, list):
                return [self._canonicalize_skill_val(s) for s in val]
            return self._canonicalize_skill_val(val)
        return val

    def _normalize_phone(self, phone: Any) -> str:
        if not phone:
            return ""
        p_str = str(phone)
        has_plus = p_str.strip().startswith("+")
        digits = re.sub(r"\D", "", p_str)
        return f"+{digits}" if has_plus else digits

    def _canonicalize_skill_val(self, skill: Any) -> Any:
        """Map alias string or skill dictionary name to canonical name."""
        if isinstance(skill, str):
            return self._aliases.get(skill.strip().lower(), skill.strip())
        if isinstance(skill, dict) and "name" in skill:
            name = str(skill["name"]).strip()
            skill_copy = dict(skill)
            skill_copy["name"] = self._aliases.get(name.lower(), name)
            return skill_copy
        return skill

    def _serialize_value(self, val: Any, include_confidence: bool) -> Any:
        """Recursively convert Pydantic models to dicts and optionally strip confidence."""
        if isinstance(val, BaseModel):
            exclude = set()
            if isinstance(val, Skill) and not include_confidence:
                exclude.add("confidence")

            res = {}
            for field_name in type(val).model_fields:
                if field_name in exclude:
                    continue
                field_val = getattr(val, field_name)
                res[field_name] = self._serialize_value(field_val, include_confidence)
            return res
        elif isinstance(val, list):
            return [self._serialize_value(item, include_confidence) for item in val]
        elif isinstance(val, dict):
            # If a dictionary has "confidence" and represents a skill, strip if needed
            res_dict = {}
            for k, v in val.items():
                if k == "confidence" and not include_confidence:
                    continue
                res_dict[k] = self._serialize_value(v, include_confidence)
            return res_dict
        return val
