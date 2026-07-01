"""Unit tests for FieldNormalizer."""

import pytest

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.processors.normalizer import FieldNormalizer


class TestFieldNormalizer:
    """Tests for FieldNormalizer processor."""

    @pytest.fixture
    def normalizer(self) -> FieldNormalizer:
        return FieldNormalizer()

    def test_order(self, normalizer: FieldNormalizer) -> None:
        assert normalizer.order == 10

    def _create_ev(self, field: str, value: any) -> Evidence:
        return Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test",
            source_candidate_id="c1",
            field_name=field,
            raw_value=value,
            confidence=1.0,
            extraction_method=ExtractionMethod.CSV_PARSE,
        )

    def test_normalize_string(self, normalizer: FieldNormalizer, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        ev = self._create_ev("full_name", "  John Doe  ")
        repo.add(ev)
        
        normalizer.process(repo, pipeline_context)
        
        assert ev.normalized_value == "John Doe"
        assert ev.raw_value == "  John Doe  "

    def test_normalize_emails(self, normalizer: FieldNormalizer, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        ev = self._create_ev("emails", ["  John@EXAMPLE.com ", "TEST@example.org "])
        repo.add(ev)
        
        normalizer.process(repo, pipeline_context)
        
        assert ev.normalized_value == ["john@example.com", "test@example.org"]

    def test_normalize_phones(self, normalizer: FieldNormalizer, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        ev = self._create_ev("phones", ["+1 (555) 123-4567", "555.987.6543"])
        repo.add(ev)
        
        normalizer.process(repo, pipeline_context)
        
        assert ev.normalized_value == ["+15551234567", "5559876543"]

    def test_normalize_location(self, normalizer: FieldNormalizer, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        ev = self._create_ev("location", {"city": " New York ", "region": "NY ", "country": " USA"})
        repo.add(ev)
        
        normalizer.process(repo, pipeline_context)
        
        assert ev.normalized_value == {"city": "New York", "region": "NY", "country": "USA"}

    def test_unsupported_field_passes_through(self, normalizer: FieldNormalizer, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        ev = self._create_ev("years_experience", 5)
        repo.add(ev)
        
        normalizer.process(repo, pipeline_context)
        
        assert ev.normalized_value == 5
