"""Base validator interface and ValidationResult model.

The validator inspects the projected output dictionary and checks it
against the type declarations, format constraints, and required-field
rules defined by the :class:`OutputConfig`.

:class:`ValidationResult` is a simple value object co-located here
because it is tightly coupled with the validator interface — every
``validate`` call returns one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from candidate_transformer.config.models import OutputConfig


class ValidationResult(BaseModel):
    """Outcome of validating a projected output dictionary.

    Attributes
    ----------
    is_valid:
        ``True`` if no errors were found.
    errors:
        Human-readable descriptions of each validation failure.
    warnings:
        Non-blocking issues worth surfacing (e.g. deprecated fields).
    """

    model_config = ConfigDict(frozen=True)

    is_valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class BaseValidator(ABC):
    """Abstract base class for output validators.

    Subclasses implement :meth:`validate` to inspect the projected
    output dict and return a :class:`ValidationResult`.  The pipeline
    orchestrator calls the validator after projection and before
    emitting the final JSON output.
    """

    @abstractmethod
    def validate(
        self,
        data: dict[str, object],
        config: OutputConfig,
    ) -> ValidationResult:
        """Validate a projected output dictionary.

        Parameters
        ----------
        data:
            The projected output dictionary to validate.
        config:
            The output configuration that describes expected types,
            required fields, and format constraints.

        Returns
        -------
        ValidationResult
            Contains ``is_valid``, ``errors``, and ``warnings``.
        """
        ...
