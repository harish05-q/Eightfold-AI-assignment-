"""Unit tests for PipelineOrchestrator."""

import pytest

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.domain.interfaces.validator import ValidationResult
from candidate_transformer.domain.models.candidate import CanonicalCandidate
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import InputManifest, SourceDescriptor
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.extractors.registry import ExtractorRegistry
from candidate_transformer.pipeline.context import PipelineContext
from candidate_transformer.pipeline.orchestrator import PipelineOrchestrator
from candidate_transformer.processors.registry import ProcessorRegistry
from candidate_transformer.projection.engine import ProjectionEngine
from candidate_transformer.validation.validator import ConfigValidator


class MockExtractor:
    @property
    def source_type(self) -> SourceType:
        return SourceType.ATS_JSON

    def extract(self, source: SourceDescriptor, ctx: PipelineContext) -> list[Evidence]:
        if source.path == "extraction_fail":
            raise RuntimeError("Extraction crashed")
        return []

class MockProcessor(BaseProcessor):
    @property
    def name(self) -> str:
        return "MockProcessor"
    
    @property
    def order(self) -> int:
        return 10
        
    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        if ctx.input_manifest.sources[0].path == "processor_fail":
            raise ValueError("Processor crash")
        if ctx.input_manifest.sources[0].path == "success":
            # Just create a dummy candidate to trigger projection
            ctx.candidates.append(CanonicalCandidate(candidate_id="mock_1"))

class MockValidator(ConfigValidator):
    def validate(self, data: dict, config: OutputConfig) -> ValidationResult:
        if data.get("candidate_id") == "mock_1":
            return ValidationResult(is_valid=False, errors=["Mock error"], warnings=["Mock warning"])
        return ValidationResult(is_valid=True)


class TestPipelineOrchestrator:
    """Tests for PipelineOrchestrator using mocked dependencies."""

    @pytest.fixture
    def orchestrator(self) -> PipelineOrchestrator:
        extractor_reg = ExtractorRegistry()
        extractor_reg.register(MockExtractor())
        
        processor_reg = ProcessorRegistry()
        processor_reg.register(MockProcessor())
        
        return PipelineOrchestrator(
            extractor_registry=extractor_reg,
            processor_registry=processor_reg,
            evidence_repo=EvidenceRepository(),
            projection_engine=ProjectionEngine(),
            validator=MockValidator(),
        )

    def test_run_success_flow(self, orchestrator: PipelineOrchestrator) -> None:
        manifest = InputManifest(sources=[SourceDescriptor(source_type=SourceType.ATS_JSON, path="success")])
        config = OutputConfig()
        
        result = orchestrator.run(manifest, config, run_id="test-run")
        
        assert result.run_id == "test-run"
        assert "total" in result.timing
        assert "extraction" in result.timing
        assert "processing" in result.timing
        assert "projection_validation" in result.timing
        assert "processor:MockProcessor" in result.timing
        
        assert len(result.candidates) == 1
        assert result.candidates[0]["candidate_id"] == "mock_1"
        
        # We injected a MockValidator that fails validation for 'mock_1'
        assert len(result.errors) == 1
        assert "validation" == result.errors[0].stage
        assert len(result.warnings) == 1
        assert "Validation warning" in result.warnings[0]

    def test_extraction_failure_is_caught(self, orchestrator: PipelineOrchestrator) -> None:
        manifest = InputManifest(sources=[SourceDescriptor(source_type=SourceType.ATS_JSON, path="extraction_fail")])
        config = OutputConfig()
        
        result = orchestrator.run(manifest, config)
        
        assert len(result.errors) == 1
        assert result.errors[0].stage == "extraction"
        assert result.errors[0].error_type == "RuntimeError"

    def test_processor_failure_is_caught(self, orchestrator: PipelineOrchestrator) -> None:
        manifest = InputManifest(sources=[SourceDescriptor(source_type=SourceType.ATS_JSON, path="processor_fail")])
        config = OutputConfig()
        
        result = orchestrator.run(manifest, config)
        
        assert len(result.errors) == 1
        assert result.errors[0].stage == "processing"
        assert result.errors[0].source == "MockProcessor"
        assert result.errors[0].error_type == "ValueError"

    def test_unknown_extractor_logs_error(self, orchestrator: PipelineOrchestrator) -> None:
        manifest = InputManifest(sources=[SourceDescriptor(source_type=SourceType.GITHUB, path="unknown_extractor")])
        config = OutputConfig()
        
        result = orchestrator.run(manifest, config)
        
        assert len(result.errors) == 1
        assert result.errors[0].stage == "extraction"
        assert "No extractor found" in result.errors[0].message
