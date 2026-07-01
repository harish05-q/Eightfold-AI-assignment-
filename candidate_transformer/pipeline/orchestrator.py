"""Pipeline Orchestrator.

The orchestrator wires together the independent layers (Extraction,
Evidence Repository, Processing, Projection, Validation) into a cohesive,
deterministic pipeline run.

It expects its dependencies to be injected at instantiation, allowing for
trivial mocking in tests and flexibility in execution environments.
"""

from dataclasses import dataclass
from typing import Any

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.interfaces.validator import BaseValidator
from candidate_transformer.domain.models.input import InputManifest
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.extractors.registry import ExtractorRegistry
from candidate_transformer.pipeline.context import PipelineContext, PipelineError
from candidate_transformer.processors.registry import ProcessorRegistry
from candidate_transformer.projection.engine import ProjectionEngine


@dataclass
class PipelineResult:
    """The final output of a single pipeline run.
    
    Contains the fully projected candidates along with comprehensive
    diagnostic metadata (errors, warnings, timings).
    """
    run_id: str
    candidates: list[dict[str, Any]]
    errors: list[PipelineError]
    warnings: list[str]
    timing: dict[str, float]


class PipelineOrchestrator:
    """Coordinates the execution of the candidate transformation pipeline."""

    def __init__(
        self,
        extractor_registry: ExtractorRegistry,
        processor_registry: ProcessorRegistry,
        evidence_repo: EvidenceRepository,
        projection_engine: ProjectionEngine,
        validator: BaseValidator,
    ) -> None:
        self.extractor_registry = extractor_registry
        self.processor_registry = processor_registry
        self.evidence_repo = evidence_repo
        self.projection_engine = projection_engine
        self.validator = validator

    def run(
        self,
        manifest: InputManifest,
        config: OutputConfig,
        run_id: str | None = None,
    ) -> PipelineResult:
        """Execute a full pipeline run for the given manifest and configuration."""
        # 1. Initialize context and state
        ctx = PipelineContext(input_manifest=manifest, output_config=config, run_id=run_id)
        self.evidence_repo.clear()
        
        ctx.start_timer("total")

        # 2. Extraction phase
        ctx.start_timer("extraction")
        for source in manifest.sources:
            try:
                extractor = self.extractor_registry.get(source.source_type)
                if not extractor:
                    ctx.add_error(
                        stage="extraction",
                        source="Orchestrator",
                        error=ValueError(f"No extractor found for source type: {source.source_type.value}")
                    )
                    continue
                    
                evidence_list = extractor.extract(source, ctx)
                self.evidence_repo.add_many(evidence_list)
            except Exception as e:
                ctx.add_error(
                    stage="extraction",
                    source=source.source_type.value,
                    error=e,
                )
        ctx.stop_timer("extraction")

        # 3. Processing phase (runs sequentially ordered by processor.order)
        ctx.start_timer("processing")
        processors = self.processor_registry.get_all()
        for processor in processors:
            ctx.start_timer(f"processor:{processor.name}")
            try:
                processor.process(self.evidence_repo, ctx)
            except Exception as e:
                ctx.add_error(
                    stage="processing",
                    source=processor.name,
                    error=e,
                )
            ctx.stop_timer(f"processor:{processor.name}")
        ctx.stop_timer("processing")

        # 4. Projection & Validation phase
        ctx.start_timer("projection_validation")
        projected_candidates: list[dict[str, Any]] = []
        
        for candidate in ctx.candidates:
            # 4a. Projection
            try:
                projected = self.projection_engine.project(candidate, config)
            except Exception as e:
                ctx.add_error(
                    stage="projection",
                    source="ProjectionEngine",
                    error=e,
                )
                continue

            # 4b. Validation
            try:
                val_result = self.validator.validate(projected, config)
                for w in val_result.warnings:
                    ctx.add_warning(f"Validation warning (candidate {candidate.candidate_id}): {w}")
                    
                if not val_result.is_valid:
                    error_msgs = "; ".join(val_result.errors)
                    ctx.add_error(
                        stage="validation",
                        source="ConfigValidator",
                        error=ValueError(f"Candidate {candidate.candidate_id} failed validation: {error_msgs}")
                    )
                    # We continue appending it to output, allowing consumer to see the 
                    # invalid shape, or we could drop it. Architecture suggests
                    # explicit error reporting rather than crashing/silently dropping.
            except Exception as e:
                ctx.add_error(
                    stage="validation",
                    source="ConfigValidator",
                    error=e,
                )
                
            projected_candidates.append(projected)
            
        ctx.stop_timer("projection_validation")
        ctx.stop_timer("total")

        # 5. Return result bundle
        return PipelineResult(
            run_id=ctx.run_id,
            candidates=projected_candidates,
            errors=ctx.errors,
            warnings=ctx.warnings,
            timing=ctx.timing,
        )
