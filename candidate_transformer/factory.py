"""Factory for assembling the complete candidate transformer pipeline."""

from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.extractors.json_extractor import ATSJsonExtractor
from candidate_transformer.extractors.csv_extractor import RecruiterCSVExtractor
from candidate_transformer.extractors.github_extractor import GitHubExtractor
from candidate_transformer.extractors.registry import ExtractorRegistry
from candidate_transformer.extractors.resume_extractor import ResumeExtractor
from candidate_transformer.pipeline.orchestrator import PipelineOrchestrator
from candidate_transformer.processors.skill_canonicalizer import SkillCanonicalizer
from candidate_transformer.processors.merger import EvidenceMerger
from candidate_transformer.processors.normalizer import FieldNormalizer
from candidate_transformer.processors.registry import ProcessorRegistry
from candidate_transformer.processors.identity_resolver import IdentityResolver
from candidate_transformer.processors.confidence_scorer import ConfidenceScorer
from candidate_transformer.projection.engine import ProjectionEngine
from candidate_transformer.validation.validator import ConfigValidator


def create_standard_orchestrator() -> PipelineOrchestrator:
    """Wire together and return the default pipeline orchestrator."""
    # 1. Setup Extractors
    extractor_reg = ExtractorRegistry()
    extractor_reg.register(RecruiterCSVExtractor())
    extractor_reg.register(ATSJsonExtractor())
    extractor_reg.register(GitHubExtractor())
    extractor_reg.register(ResumeExtractor())

    # 2. Setup Processors (they sort themselves by .order)
    processor_reg = ProcessorRegistry()
    processor_reg.register(FieldNormalizer())
    processor_reg.register(SkillCanonicalizer())
    processor_reg.register(IdentityResolver())
    processor_reg.register(EvidenceMerger())
    processor_reg.register(ConfidenceScorer())

    # 3. Assemble Orchestrator
    return PipelineOrchestrator(
        extractor_registry=extractor_reg,
        processor_registry=processor_reg,
        evidence_repo=EvidenceRepository(),
        projection_engine=ProjectionEngine(),
        validator=ConfigValidator(),
    )
