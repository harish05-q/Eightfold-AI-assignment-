"""Domain enumerations for the candidate transformer pipeline.

All enums inherit from ``str`` so their ``.value`` is a plain string,
enabling clean JSON serialization and use as dictionary keys without
manual conversion.  No external dependencies — this module belongs
to the innermost domain ring.
"""

from enum import Enum


class SourceType(str, Enum):
    """Identifies the origin type of extracted data.

    Each value corresponds to exactly one extractor implementation
    registered in the ExtractorRegistry.  The string values are used
    as keys in the ``source_priority`` configuration mapping.
    """

    RECRUITER_CSV = "csv"
    ATS_JSON = "ats"
    GITHUB = "github"
    RESUME = "resume"


class MissingPolicy(str, Enum):
    """Defines behaviour when a projected field has no value.

    Configured per-output via ``OutputConfig.on_missing``.

    * ``NULL``  — include the field with a ``null`` JSON value.
    * ``OMIT``  — exclude the field entirely from the output dict.
    * ``ERROR`` — raise a validation error so the caller knows.
    """

    NULL = "null"
    OMIT = "omit"
    ERROR = "error"


class ExtractionMethod(str, Enum):
    """Records *how* a piece of evidence was obtained from its source.

    Stored on each :class:`Evidence` object and propagated into the
    provenance record so every output value is traceable back to an
    extraction technique.
    """

    CSV_PARSE = "csv_parse"
    JSON_PARSE = "json_parse"
    API_FETCH = "api_fetch"
    TEXT_PARSE = "text_parse"
    PDF_PARSE = "pdf_parse"
