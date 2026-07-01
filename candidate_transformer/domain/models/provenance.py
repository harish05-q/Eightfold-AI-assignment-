"""Provenance model — records the lineage of every canonical field value.

Each :class:`ProvenanceRecord` answers the question *"Where did this
field value come from?"* by capturing the source identifier, extraction
method, and the confidence that was assigned at merge time.

Instances are **frozen** (immutable) because provenance is historical
evidence that must never be altered after creation.
"""

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceRecord(BaseModel):
    """Records the origin of a single field value in the canonical profile.

    Attributes
    ----------
    field:
        The canonical field name (e.g. ``"full_name"``, ``"emails"``).
    source:
        The source type value that provided the winning value
        (e.g. ``"csv"``, ``"ats"``, ``"github"``).
    method:
        The extraction method used (mirrors :class:`ExtractionMethod` values).
    confidence:
        The confidence score assigned to this value at merge time (0.0–1.0).
    """

    model_config = ConfigDict(frozen=True)

    field: str
    source: str
    method: str
    confidence: float = Field(ge=0.0, le=1.0)
