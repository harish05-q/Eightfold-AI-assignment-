"""Domain-specific exceptions for the candidate transformer pipeline.

Exception hierarchy
-------------------
::

    CandidateTransformerError
    ├── ExtractionError
    ├── NormalizationError
    ├── MergeConflictError
    ├── ValidationError
    └── ConfigurationError

Every exception accepts an optional ``context`` dict that carries
structured metadata (file path, line number, field name, etc.) to
aid debugging without encoding those details in the message string.
"""


class CandidateTransformerError(Exception):
    """Base exception for all candidate transformer errors.

    Parameters
    ----------
    message:
        Human-readable error description.
    context:
        Optional mapping of structured metadata for logging and diagnostics.
    """

    def __init__(
        self,
        message: str,
        context: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.context: dict[str, object] = context or {}


class ExtractionError(CandidateTransformerError):
    """Raised when data extraction fails for a source.

    The pipeline orchestrator catches this per-source, logs the failure,
    and continues processing the remaining sources so that a single bad
    input does not crash the entire run.
    """


class NormalizationError(CandidateTransformerError):
    """Raised when field normalization fails.

    The normalizer catches this per-field and falls back to the raw value
    with a reduced confidence score.  Data is never invented.
    """


class MergeConflictError(CandidateTransformerError):
    """Raised when a merge conflict cannot be resolved deterministically.

    In practice this should never surface because the merger always
    resolves via the configured source-priority ranking, but it exists
    as a safety net for unexpected edge cases.
    """


class ValidationError(CandidateTransformerError):
    """Raised when the projected output fails schema validation.

    Carries the list of individual validation failures in ``context``
    under the ``"errors"`` key.
    """


class ConfigurationError(CandidateTransformerError):
    """Raised when pipeline or output configuration is invalid.

    Raised eagerly at startup so mis-configurations are caught before
    any data processing begins.
    """
