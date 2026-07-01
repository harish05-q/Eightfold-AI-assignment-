"""Processor Registry layer.

Manages the registration and ordered execution of Evidence processors.
Processors apply transformations, grouping, or resolution logic 
over the extracted Evidence.
"""

import logging

from candidate_transformer.domain.interfaces.processor import BaseProcessor


class ProcessorRegistry:
    """Registry that maintains an ordered list of Processors.
    
    Processors are sorted by their `order` property to ensure deterministic 
    execution (e.g. Normalization must happen before Identity Resolution, 
    which must happen before Merging).
    """

    def __init__(self) -> None:
        self._processors: list[BaseProcessor] = []
        self._logger = logging.getLogger("candidate_transformer.processors.registry")

    def register(self, processor: BaseProcessor) -> None:
        """Register a processor into the pipeline.
        
        Registers the processor and immediately re-sorts the internal list 
        based on the processor's `order` property.
        """
        # Ensure we don't register the same type twice
        for existing in self._processors:
            if type(existing) == type(processor):
                self._logger.warning(
                    "Processor %s is already registered. Overwriting.", 
                    type(processor).__name__
                )
                self._processors.remove(existing)
                break
                
        self._processors.append(processor)
        # Sort by processor order to enforce execution sequence
        self._processors.sort(key=lambda p: p.order)
        
        self._logger.debug(
            "Registered processor %s (order=%d)",
            type(processor).__name__,
            processor.order,
        )

    def get_all(self) -> list[BaseProcessor]:
        """Return the ordered list of registered processors."""
        return list(self._processors)

    def clear(self) -> None:
        """Remove all registered processors."""
        self._processors.clear()
