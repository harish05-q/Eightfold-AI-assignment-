"""Confidence Scorer Processor.

Evaluates the merged CanonicalCandidates and logs warnings for candidates
that are exceptionally sparse or have very low confidence data.
"""

from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext


class ConfidenceScorer(BaseProcessor):
    """Scores candidate confidence and logs warnings for sparse profiles."""

    @property
    def name(self) -> str:
        return "ConfidenceScorer"

    @property
    def order(self) -> int:
        return 50  # Runs after EvidenceMerger

    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        """Evaluate merged candidates for data completeness."""
        for candidate in ctx.candidates:
            # Check for critical missing fields
            missing_critical = []
            if not candidate.full_name:
                missing_critical.append("full_name")
            if not candidate.emails and not candidate.phones:
                missing_critical.append("contact_info (email/phone)")
                
            if missing_critical:
                ctx.add_warning(
                    f"Candidate {candidate.candidate_id} is missing critical fields: "
                    f"{', '.join(missing_critical)}"
                )
                
            # Check skill confidence
            if candidate.skills:
                low_conf_skills = [s.name for s in candidate.skills if s.confidence < 0.5]
                if low_conf_skills:
                    ctx.logger.debug(
                        "Candidate %s has low confidence skills: %s",
                        candidate.candidate_id,
                        ", ".join(low_conf_skills)
                    )
