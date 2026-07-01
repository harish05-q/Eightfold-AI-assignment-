"""Unit tests for SkillCanonicalizer."""

from pathlib import Path
import pytest
import json

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.processors.skill_canonicalizer import SkillCanonicalizer


class TestSkillCanonicalizer:
    """Tests for SkillCanonicalizer processor."""

    def test_order(self) -> None:
        assert SkillCanonicalizer().order == 20

    def test_canonicalize_skills_with_aliases(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Test skill canonicalization using a mocked alias file."""
        # Create a mock aliases file
        aliases_file = tmp_path / "skill_aliases.json"
        aliases_data = {
            "react.js": "React",
            "node": "Node.js"
        }
        aliases_file.write_text(json.dumps(aliases_data), encoding="utf-8")

        repo = EvidenceRepository()
        ev = Evidence.create(
            source_type=SourceType.GITHUB,
            source_ref="test",
            source_candidate_id="c1",
            field_name="skills",
            raw_value=[
                {"name": "React.js", "confidence": 0.8, "sources": ["github"]},
                {"name": "node", "confidence": 0.9, "sources": ["github"]},
                {"name": "Python", "confidence": 0.9, "sources": ["github"]},
            ],
            confidence=1.0,
            extraction_method=ExtractionMethod.JSON_PARSE,
        )
        repo.add(ev)

        processor = SkillCanonicalizer(aliases_path=aliases_file)
        processor.process(repo, pipeline_context)

        assert ev.normalized_value is not None
        skills = ev.normalized_value
        assert len(skills) == 3
        names = [s["name"] for s in skills]
        
        # Check canonicalized names
        assert "React" in names
        assert "Node.js" in names
        assert "Python" in names  # Unchanged
        
        # Check original structure is preserved
        react_skill = next(s for s in skills if s["name"] == "React")
        assert react_skill["confidence"] == 0.8
        assert react_skill["sources"] == ["github"]

    def test_canonicalize_handles_missing_file(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Missing alias file should just pass values through untouched."""
        missing_file = tmp_path / "does_not_exist.json"
        
        repo = EvidenceRepository()
        ev = Evidence.create(
            source_type=SourceType.GITHUB,
            source_ref="test",
            source_candidate_id="c1",
            field_name="skills",
            raw_value=[{"name": "react.js", "confidence": 0.8, "sources": ["github"]}],
            confidence=1.0,
            extraction_method=ExtractionMethod.JSON_PARSE,
        )
        repo.add(ev)

        processor = SkillCanonicalizer(aliases_path=missing_file)
        processor.process(repo, pipeline_context)

        # Name remains untouched
        assert ev.normalized_value[0]["name"] == "react.js"
