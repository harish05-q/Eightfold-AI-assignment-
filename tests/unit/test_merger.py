"""Unit tests for EvidenceMerger."""

import pytest

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.processors.merger import EvidenceMerger


class TestEvidenceMerger:
    """Tests for EvidenceMerger processor."""

    def test_order(self) -> None:
        assert EvidenceMerger().order == 40

    def _create_ev(self, cid: str, field: str, value: any, source: SourceType, conf: float) -> Evidence:
        return Evidence.create(
            source_type=source,
            source_ref="test",
            source_candidate_id=cid,
            field_name=field,
            raw_value=value,
            confidence=conf,
            extraction_method=ExtractionMethod.JSON_PARSE,
        )

    def test_merge_scalar_priority(self) -> None:
        """Tests that the highest priority source wins scalar fields."""
        repo = EvidenceRepository()
        # ATS has priority 100, Resume 90
        repo.add(self._create_ev("ats1", "full_name", "ATS Name", SourceType.ATS_JSON, 0.9))
        repo.add(self._create_ev("res1", "full_name", "Resume Name", SourceType.RESUME, 0.9))
        
        ctx = PipelineContext(input_manifest=None, output_config=OutputConfig(
            source_priority={"ats": 100, "resume": 90}
        ))
        ctx.candidate_groups = {"uid1": ["ats1", "res1"]}
        
        processor = EvidenceMerger()
        processor.process(repo, ctx)
        
        assert len(ctx.candidates) == 1
        assert ctx.candidates[0].full_name == "ATS Name"

    def test_merge_lists_deduplicates(self) -> None:
        repo = EvidenceRepository()
        repo.add(self._create_ev("ats1", "emails", ["a@example.com"], SourceType.ATS_JSON, 0.9))
        repo.add(self._create_ev("res1", "emails", ["b@example.com", "a@example.com"], SourceType.RESUME, 0.9))
        
        ctx = PipelineContext(input_manifest=None, output_config=OutputConfig())
        ctx.candidate_groups = {"uid1": ["ats1", "res1"]}
        
        processor = EvidenceMerger()
        processor.process(repo, ctx)
        
        emails = ctx.candidates[0].emails
        assert len(emails) == 2
        assert set(emails) == {"a@example.com", "b@example.com"}

    def test_merge_skills_averages_confidence(self) -> None:
        repo = EvidenceRepository()
        # Same skill from two sources
        repo.add(self._create_ev("ats1", "skills", [{"name": "Python", "confidence": 0.8}], SourceType.ATS_JSON, 0.8))
        repo.add(self._create_ev("gh1", "skills", [{"name": "Python", "confidence": 1.0}], SourceType.GITHUB, 1.0))
        
        ctx = PipelineContext(input_manifest=None, output_config=OutputConfig())
        ctx.candidate_groups = {"uid1": ["ats1", "gh1"]}
        
        processor = EvidenceMerger()
        processor.process(repo, ctx)
        
        skills = ctx.candidates[0].skills
        assert len(skills) == 1
        assert skills[0].name == "Python"
        assert skills[0].confidence == 0.9  # Average of 0.8 and 1.0
        assert set(skills[0].sources) == {"ats", "github"}
