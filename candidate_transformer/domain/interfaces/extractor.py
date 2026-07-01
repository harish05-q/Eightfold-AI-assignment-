"""Base extractor interface.

Every concrete extractor (CSV, ATS JSON, GitHub, Resume) implements
this abstract base class.  The :class:`ExtractorRegistry` stores
implementations keyed by :attr:`source_type`, enabling the pipeline
orchestrator to dynamically select the right extractor for each input
without hard-coding any source-specific logic (Open/Closed Principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import SourceDescriptor

if TYPE_CHECKING:
    from candidate_transformer.pipeline.context import PipelineContext


class BaseExtractor(ABC):
    """Abstract base class for all source extractors.

    Subclasses must:

    1. Set :attr:`source_type` to the exact :class:`SourceType` they handle.
    2. Implement :meth:`extract` to parse the source and return a list of
       :class:`Evidence` objects — one per extracted field per candidate
       record found in the source.

    The default :meth:`can_handle` checks whether the given source
    descriptor's type matches this extractor's type.  Override it if
    additional checks (e.g. file-extension validation) are needed.
    """

    @property
    @abstractmethod
    def source_type(self) -> SourceType:
        """The source type this extractor is responsible for."""
        ...

    @abstractmethod
    def extract(
        self,
        source: SourceDescriptor,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Extract evidence from the given source.

        Parameters
        ----------
        source:
            Descriptor containing the source path/URL and metadata.
        ctx:
            Pipeline context for logging warnings and recording errors.

        Returns
        -------
        list[Evidence]
            One evidence object per extracted field per candidate
            record.  May be empty if the source contains no usable
            data.

        Raises
        ------
        ExtractionError
            When the source is fundamentally unreadable (e.g. file
            not found).  The orchestrator catches this and continues
            with remaining sources.
        """
        ...

    def can_handle(self, source: SourceDescriptor) -> bool:
        """Check whether this extractor can process the given source.

        The default implementation compares source types.  Override
        for additional validation (e.g. checking file extensions).
        """
        return source.source_type == self.source_type
