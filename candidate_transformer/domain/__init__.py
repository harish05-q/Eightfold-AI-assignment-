"""Domain layer — core business models, interfaces, and enumerations.

This is the innermost ring of the Clean Architecture. All other layers
depend inward on these models and interfaces; this layer never imports
from extractors, processors, pipeline, or infrastructure modules.

Dependencies: pydantic (for model validation and serialization).
"""
