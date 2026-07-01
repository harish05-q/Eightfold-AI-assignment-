"""Domain models — Evidence, CanonicalCandidate, ProvenanceRecord, and input descriptors.

Re-exports every public model so that consumers can write::

    from candidate_transformer.domain.models import Evidence, CanonicalCandidate
"""

from candidate_transformer.domain.models.candidate import (
    CanonicalCandidate,
    Education,
    Experience,
    Links,
    Location,
    Skill,
)
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import InputManifest, SourceDescriptor
from candidate_transformer.domain.models.provenance import ProvenanceRecord

__all__ = [
    "CanonicalCandidate",
    "Education",
    "Evidence",
    "Experience",
    "InputManifest",
    "Links",
    "Location",
    "ProvenanceRecord",
    "Skill",
    "SourceDescriptor",
]
