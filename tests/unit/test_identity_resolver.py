"""Unit tests for IdentityResolver."""

import pytest

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.processors.identity_resolver import IdentityResolver


class TestIdentityResolver:
    """Tests for IdentityResolver processor."""

    def test_order(self) -> None:
        assert IdentityResolver().order == 30

    def _create_ev(self, cid: str, field: str, value: any, source: SourceType = SourceType.ATS_JSON) -> Evidence:
        return Evidence.create(
            source_type=source,
            source_ref="test",
            source_candidate_id=cid,
            field_name=field,
            raw_value=value,
            confidence=1.0,
            extraction_method=ExtractionMethod.JSON_PARSE,
        )

    def test_group_by_email(self, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        # Candidate 1 (ATS)
        repo.add(self._create_ev("ats_c1", "emails", ["john@example.com"]))
        repo.add(self._create_ev("ats_c1", "full_name", "John Doe"))
        # Candidate 2 (GitHub) - shares email
        repo.add(self._create_ev("gh_c1", "emails", ["john@example.com"], SourceType.GITHUB))
        
        processor = IdentityResolver()
        processor.process(repo, pipeline_context)
        
        # Should merge into 1 unified group
        groups = list(pipeline_context.candidate_groups.values())
        assert len(groups) == 1
        assert set(groups[0]) == {"ats_c1", "gh_c1"}

    def test_group_by_phone(self, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        # Candidate 1 (ATS)
        repo.add(self._create_ev("ats_c1", "phones", ["555-1234"]))
        # Candidate 2 (Resume) - shares phone
        repo.add(self._create_ev("res_c1", "phones", ["555-1234"], SourceType.RESUME))
        
        processor = IdentityResolver()
        processor.process(repo, pipeline_context)
        
        groups = list(pipeline_context.candidate_groups.values())
        assert len(groups) == 1
        assert set(groups[0]) == {"ats_c1", "res_c1"}

    def test_group_by_exact_name(self, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        # Candidate 1
        repo.add(self._create_ev("c1", "full_name", "Alice Smith"))
        # Candidate 2 - shares name exactly
        repo.add(self._create_ev("c2", "full_name", "Alice Smith"))
        
        processor = IdentityResolver()
        processor.process(repo, pipeline_context)
        
        groups = list(pipeline_context.candidate_groups.values())
        assert len(groups) == 1
        assert set(groups[0]) == {"c1", "c2"}

    def test_no_overlap_creates_separate_groups(self, pipeline_context: PipelineContext) -> None:
        repo = EvidenceRepository()
        repo.add(self._create_ev("c1", "emails", ["alice@example.com"]))
        repo.add(self._create_ev("c2", "emails", ["bob@example.com"]))
        
        processor = IdentityResolver()
        processor.process(repo, pipeline_context)
        
        groups = list(pipeline_context.candidate_groups.values())
        assert len(groups) == 2
