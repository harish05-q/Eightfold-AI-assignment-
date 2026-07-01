"""Domain interfaces — BaseExtractor, BaseProcessor, BaseValidator.

Re-exports every abstract base class so that consumers can write::

    from candidate_transformer.domain.interfaces import BaseExtractor
"""

from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.domain.interfaces.validator import (
    BaseValidator,
    ValidationResult,
)

__all__ = [
    "BaseExtractor",
    "BaseProcessor",
    "BaseValidator",
    "ValidationResult",
]
