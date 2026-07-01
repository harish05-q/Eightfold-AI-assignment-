"""Evidence model — the atomic unit of extracted candidate data.

Every piece of data extracted from any source is represented as an
:class:`Evidence` object.  This is the foundational abstraction that
enables provenance tracking, conflict resolution, confidence scoring,
and deterministic behaviour across the entire pipeline.

**Mutability contract**: Evidence objects are mutable so that the
normaliser can set :attr:`normalized_value` and the confidence scorer
can adjust :attr:`confidence`.  All other pipeline stages treat
evidence as read-only.
"""

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from candidate_transformer.domain.enums import ExtractionMethod, SourceType


class Evidence(BaseModel):
    """A single fact extracted from a single source about one candidate field.

    Attributes
    ----------
    evidence_id:
        Deterministic identifier derived from content attributes via
        :meth:`build_id`.  Ensures same inputs → same IDs.
    source_type:
        Which source type this evidence was extracted from.
    source_ref:
        File path or URL of the concrete source artefact.
    source_candidate_id:
        Per-source identifier that groups fields extracted from the
        same source record (e.g. same CSV row, same ATS JSON object).
    field_name:
        The canonical field name this evidence maps to (e.g. ``"full_name"``).
    raw_value:
        The original value exactly as extracted from the source.
    normalized_value:
        The value after normalisation (E.164, YYYY-MM, ISO-3166, etc.).
        ``None`` until the normaliser processes this evidence.
    confidence:
        Confidence score between 0.0 and 1.0 (inclusive).
    extraction_method:
        How this value was extracted from its source.
    timestamp:
        UTC timestamp of when this evidence was created.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    evidence_id: str
    source_type: SourceType
    source_ref: str
    source_candidate_id: str
    field_name: str
    raw_value: Any
    normalized_value: Any | None = None
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    extraction_method: ExtractionMethod
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # ------------------------------------------------------------------
    # Factory helpers
    # ------------------------------------------------------------------

    @staticmethod
    def build_id(
        source_type: SourceType,
        source_ref: str,
        source_candidate_id: str,
        field_name: str,
    ) -> str:
        """Build a deterministic evidence ID from content attributes.

        The ID is a 16-character hex prefix of the SHA-256 hash of the
        concatenated attributes.  This guarantees that the same input
        always produces the same evidence ID, satisfying the determinism
        requirement.

        Parameters
        ----------
        source_type:
            Source type enum value.
        source_ref:
            File path or URL of the source.
        source_candidate_id:
            Per-source candidate identifier.
        field_name:
            Canonical field name.

        Returns
        -------
        str
            16-character hexadecimal ID.
        """
        content = (
            f"{source_type.value}:{source_ref}"
            f":{source_candidate_id}:{field_name}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def create(
        cls,
        *,
        source_type: SourceType,
        source_ref: str,
        source_candidate_id: str,
        field_name: str,
        raw_value: Any,
        confidence: float = 0.5,
        extraction_method: ExtractionMethod,
    ) -> "Evidence":
        """Convenience factory that auto-computes a deterministic evidence ID.

        All parameters are keyword-only to prevent positional mis-ordering.

        Parameters
        ----------
        source_type:
            Source type enum value.
        source_ref:
            File path or URL of the source.
        source_candidate_id:
            Per-source candidate identifier.
        field_name:
            Canonical field name.
        raw_value:
            The raw extracted value.
        confidence:
            Initial confidence score (0.0–1.0). Defaults to 0.5.
        extraction_method:
            How this value was extracted.

        Returns
        -------
        Evidence
            Fully constructed evidence with a deterministic ID.
        """
        evidence_id = cls.build_id(
            source_type, source_ref, source_candidate_id, field_name,
        )
        return cls(
            evidence_id=evidence_id,
            source_type=source_type,
            source_ref=source_ref,
            source_candidate_id=source_candidate_id,
            field_name=field_name,
            raw_value=raw_value,
            confidence=confidence,
            extraction_method=extraction_method,
        )
