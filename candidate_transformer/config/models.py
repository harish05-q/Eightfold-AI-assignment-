"""Output configuration models — OutputConfig and FieldSpec.

These Pydantic v2 models describe the runtime output configuration
that controls how the Projection Engine reshapes the canonical candidate
into the final JSON output.  They are loaded by :class:`ConfigLoader`
from a JSON file or constructed programmatically.

Key design note: the ``"from"`` key in the JSON config is a Python
reserved word.  We use ``from_path`` as the Python attribute name with
a Pydantic alias so that JSON files can use the natural ``"from"`` key.
"""

from pydantic import BaseModel, ConfigDict, Field

from candidate_transformer.domain.enums import MissingPolicy


class FieldSpec(BaseModel):
    """Specifies one field in the projected output.

    Attributes
    ----------
    path:
        The key name in the output JSON (e.g. ``"full_name"``,
        ``"primary_email"``).
    from_path:
        Dot-path or bracket-path into the canonical model to read the
        value from (e.g. ``"emails[0]"``, ``"skills[].name"``).
        Defaults to ``path`` if not specified.
    type:
        Expected output type — ``"string"``, ``"string[]"``,
        ``"number"``, ``"object"``, ``"object[]"``.
    required:
        If ``True``, the validator will reject output where this field
        is missing.
    normalize:
        Optional per-field normalisation to apply during projection.
        Supported values: ``"E164"`` (phones), ``"canonical"`` (skills).
    """

    model_config = ConfigDict(populate_by_name=True)

    path: str
    from_path: str | None = Field(default=None, alias="from")
    type: str = "string"
    required: bool = False
    normalize: str | None = None

    @property
    def resolved_from(self) -> str:
        """Return the canonical path to read from, defaulting to ``path``."""
        return self.from_path if self.from_path is not None else self.path


class OutputConfig(BaseModel):
    """Runtime configuration that controls the pipeline's output shape.

    Attributes
    ----------
    fields:
        List of field specifications defining which fields appear in
        the output and how they are sourced from the canonical model.
        An empty list means "emit all default fields".
    include_confidence:
        Whether to include ``overall_confidence`` and per-skill
        confidence in the output.
    on_missing:
        Global policy for missing values — ``null``, ``omit``, or
        ``error``.
    source_priority:
        Maps source-type keys (e.g. ``"ats"``, ``"csv"``) to integer
        priority weights.  Higher values win during merge conflict
        resolution.  Configuration-driven per user requirement.
    """

    fields: list[FieldSpec] = Field(default_factory=list)
    include_confidence: bool = True
    on_missing: MissingPolicy = MissingPolicy.NULL
    source_priority: dict[str, int] = Field(
        default_factory=lambda: {
            "ats": 100,
            "resume": 90,
            "github": 80,
            "csv": 70,
        },
    )

    def get_priority(self, source_type_value: str) -> int:
        """Return the merge priority for a given source type value.

        Returns 0 for unknown source types so they always lose to
        configured sources.
        """
        return self.source_priority.get(source_type_value, 0)
