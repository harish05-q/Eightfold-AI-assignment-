"""Extractor registry — maps source types to extractor implementations.

Implements the **Registry Pattern** so that new extractors can be added
by calling :meth:`register` without modifying the pipeline orchestrator
or any existing extractor (Open/Closed Principle).
"""

import logging

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.models.input import InputManifest, SourceDescriptor


class ExtractorRegistry:
    """Registry that maps :class:`SourceType` to :class:`BaseExtractor` instances.

    Usage::

        registry = ExtractorRegistry()
        registry.register(CSVExtractor())
        registry.register(ATSJsonExtractor())

        # Later, the orchestrator queries:
        pairs = registry.get_for_manifest(manifest)
        for source, extractor in pairs:
            evidences = extractor.extract(source, ctx)
    """

    def __init__(self) -> None:
        self._extractors: dict[SourceType, BaseExtractor] = {}
        self._logger = logging.getLogger("candidate_transformer.extractors.registry")

    def register(self, extractor: BaseExtractor) -> None:
        """Register an extractor for its declared source type.

        Overwrites any previously registered extractor for the same type.
        """
        self._extractors[extractor.source_type] = extractor
        self._logger.debug(
            "Registered extractor %s for source type '%s'",
            type(extractor).__name__,
            extractor.source_type.value,
        )

    def get(self, source_type: SourceType) -> BaseExtractor | None:
        """Return the extractor for the given source type, or ``None``."""
        return self._extractors.get(source_type)

    def get_for_manifest(
        self,
        manifest: InputManifest,
    ) -> list[tuple[SourceDescriptor, BaseExtractor]]:
        """Return ``(source, extractor)`` pairs for every manifest source
        that has a registered extractor.

        Sources without a matching extractor are silently skipped — the
        orchestrator logs a warning for those.
        """
        pairs: list[tuple[SourceDescriptor, BaseExtractor]] = []
        for source in manifest.sources:
            extractor = self._extractors.get(source.source_type)
            if extractor is not None:
                pairs.append((source, extractor))
        return pairs

    def has(self, source_type: SourceType) -> bool:
        """Check whether an extractor is registered for the given type."""
        return source_type in self._extractors

    @property
    def registered_types(self) -> list[SourceType]:
        """List all source types that have a registered extractor."""
        return list(self._extractors.keys())
