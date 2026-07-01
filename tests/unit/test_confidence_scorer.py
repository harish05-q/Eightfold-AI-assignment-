"""Unit tests for ConfidenceScorer."""

import pytest

from candidate_transformer.domain.models.candidate import CanonicalCandidate, Skill
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.processors.confidence_scorer import ConfidenceScorer


class TestConfidenceScorer:
    """Tests for ConfidenceScorer processor."""

    def test_order(self) -> None:
        assert ConfidenceScorer().order == 50

    def test_process_logs_warning_for_sparse_profile(self, pipeline_context: PipelineContext) -> None:
        # Create a sparse candidate
        candidate = CanonicalCandidate(
            candidate_id="uid1",
            full_name=None,
            emails=[],
            phones=[],
        )
        pipeline_context.candidates = [candidate]
        
        processor = ConfidenceScorer()
        processor.process(None, pipeline_context)  # repo not needed for scorer
        
        assert len(pipeline_context.warnings) == 1
        assert "uid1" in pipeline_context.warnings[0]
        assert "full_name" in pipeline_context.warnings[0]
        assert "contact_info" in pipeline_context.warnings[0]

    def test_process_clean_profile_no_warnings(self, pipeline_context: PipelineContext) -> None:
        candidate = CanonicalCandidate(
            candidate_id="uid2",
            full_name="John",
            emails=["j@example.com"],
            skills=[Skill(name="Python", confidence=0.9, sources=["ats"])]
        )
        pipeline_context.candidates = [candidate]
        
        processor = ConfidenceScorer()
        processor.process(None, pipeline_context)
        
        assert len(pipeline_context.warnings) == 0
