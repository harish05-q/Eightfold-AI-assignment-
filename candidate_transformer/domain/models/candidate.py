"""Canonical candidate model and its constituent sub-models.

The :class:`CanonicalCandidate` is the **internal**, source-agnostic
representation produced by the merger.  It always carries every field
defined by the default output schema, even when values are ``None``.

The **Projection Engine** (a separate layer) maps this model to the
external output shape dictated by the runtime configuration.  This
separation ensures that the internal model is stable regardless of
how many output formats are supported.
"""

from pydantic import BaseModel, Field

from candidate_transformer.domain.models.provenance import ProvenanceRecord


class Location(BaseModel):
    """Geographic location with optional granularity.

    ``country`` uses ISO-3166 alpha-2 codes (e.g. ``"US"``, ``"IN"``).
    """

    city: str | None = None
    region: str | None = None
    country: str | None = None


class Links(BaseModel):
    """Collection of web profile links associated with a candidate."""

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None
    other: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    """A canonicalised skill with confidence and source provenance.

    ``name`` holds the canonical skill name (e.g. ``"JavaScript"``
    rather than ``"JS"`` or ``"js"``).
    """

    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    sources: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    """A single work-experience entry.

    ``start`` and ``end`` are normalised to ``YYYY-MM`` format.
    """

    company: str
    title: str
    start: str | None = None
    end: str | None = None
    summary: str | None = None


class Education(BaseModel):
    """A single education entry."""

    institution: str
    degree: str | None = None
    field: str | None = None
    end_year: int | None = None


class CanonicalCandidate(BaseModel):
    """The merged, source-agnostic candidate profile.

    Every field defaults to its zero-value (``None``, empty list, or
    ``0.0``) so that a partially-populated candidate is always valid.
    The overall_confidence of 0.0 signals "no data available" — the
    confidence scorer updates this after merging.

    Attributes
    ----------
    candidate_id:
        Deterministic identifier derived from the candidate's primary
        matching key (email hash, phone hash, or name hash).
    provenance:
        One record per populated field explaining its origin.
    overall_confidence:
        Weighted average of per-field confidence scores.
    """

    candidate_id: str
    full_name: str | None = None
    emails: list[str] = Field(default_factory=list)
    phones: list[str] = Field(default_factory=list)
    location: Location = Field(default_factory=Location)
    links: Links = Field(default_factory=Links)
    headline: str | None = None
    years_experience: float | None = None
    skills: list[Skill] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    provenance: list[ProvenanceRecord] = Field(default_factory=list)
    overall_confidence: float = Field(ge=0.0, le=1.0, default=0.0)
