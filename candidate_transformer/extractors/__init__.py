"""Extractors layer — source-specific data extraction implementations.

Each extractor reads one source format and produces a list of
:class:`Evidence` objects.  Extractors are registered in the
:class:`ExtractorRegistry` and selected at runtime based on the
input manifest's source types.
"""

from candidate_transformer.extractors.registry import ExtractorRegistry

__all__ = ["ExtractorRegistry"]
