"""Input descriptor models — SourceDescriptor and InputManifest.

These models describe *what* the pipeline should ingest.  They are
constructed from the CLI arguments or API request body and passed to
the :class:`PipelineOrchestrator` to determine which extractors to
activate and in what priority order.
"""

from pydantic import BaseModel, Field

from candidate_transformer.domain.enums import SourceType


class SourceDescriptor(BaseModel):
    """Describes a single input source to be processed.

    Attributes
    ----------
    source_type:
        The type of source (CSV, ATS JSON, GitHub, Resume).
    path:
        File-system path or URL to the source.
    priority:
        Merge priority for this source (0–100, higher wins).
        Overridden by the ``source_priority`` configuration if present.
    """

    source_type: SourceType
    path: str
    priority: int = Field(default=50, ge=0, le=100)


class InputManifest(BaseModel):
    """Collection of all input sources for a single pipeline run.

    The orchestrator iterates over ``sources`` and activates the
    matching extractor for each one.
    """

    sources: list[SourceDescriptor] = Field(default_factory=list)
