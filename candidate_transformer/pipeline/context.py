"""Pipeline context — shared mutable state across all pipeline stages.

The :class:`PipelineContext` is created once per pipeline run and
threaded through every extractor, processor, projector, and validator.
It carries:

* **Configuration** — the input manifest and output config (including
  source priority).
* **Error/warning log** — structured records of every non-fatal issue
  encountered during the run.
* **Timing metrics** — elapsed wall-clock time per pipeline stage.
* **Intermediate results** — candidate identity groups and merged
  canonical candidates, written by processors and consumed downstream.

The context is intentionally a plain class (not a Pydantic model)
because it has mutable state and behavioural methods.
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.candidate import CanonicalCandidate
from candidate_transformer.domain.models.input import InputManifest


@dataclass
class PipelineError:
    """Structured record of a non-fatal pipeline error.

    Attributes
    ----------
    stage:
        Pipeline stage where the error occurred
        (e.g. ``"extraction"``, ``"normalisation"``).
    source:
        Identifier for the source or component that failed
        (e.g. ``"csv_extractor"``, ``"phone_normaliser"``).
    error_type:
        The exception class name (e.g. ``"ExtractionError"``).
    message:
        Human-readable error description.
    timestamp:
        UTC time when the error was recorded.
    """

    stage: str
    source: str
    error_type: str
    message: str
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


class PipelineContext:
    """Shared mutable state for a single pipeline run.

    Parameters
    ----------
    input_manifest:
        Describes all input sources to process.
    output_config:
        Controls output shape, source priority, and missing-value policy.
    logger:
        Optional logger instance.  Falls back to the package-level
        ``candidate_transformer`` logger.
    run_id:
        Optional fixed run ID for deterministic testing.  Defaults to
        a random UUID (run IDs are for observability only and do not
        affect output determinism).
    """

    def __init__(
        self,
        input_manifest: InputManifest,
        output_config: OutputConfig,
        logger: logging.Logger | None = None,
        run_id: str | None = None,
    ) -> None:
        self.run_id: str = run_id or str(uuid.uuid4())
        self.input_manifest: InputManifest = input_manifest
        self.output_config: OutputConfig = output_config
        self.logger: logging.Logger = (
            logger or logging.getLogger("candidate_transformer")
        )

        # Error and warning tracking
        self.errors: list[PipelineError] = []
        self.warnings: list[str] = []

        # Timing metrics (stage name → elapsed seconds)
        self._active_timers: dict[str, float] = {}
        self.timing: dict[str, float] = {}

        # Intermediate results set by processors
        # IdentityResolver writes: unified_id → [source_candidate_ids]
        self.candidate_groups: dict[str, list[str]] = {}
        # EvidenceMerger writes: merged canonical candidates
        self.candidates: list[CanonicalCandidate] = []

    # ------------------------------------------------------------------
    # Error / warning helpers
    # ------------------------------------------------------------------

    def add_error(
        self,
        stage: str,
        source: str,
        error: Exception,
    ) -> None:
        """Record a non-fatal error and log it.

        Parameters
        ----------
        stage:
            Pipeline stage name (e.g. ``"extraction"``).
        source:
            Source or component identifier (e.g. ``"csv_extractor"``).
        error:
            The caught exception.
        """
        pipeline_error = PipelineError(
            stage=stage,
            source=source,
            error_type=type(error).__name__,
            message=str(error),
        )
        self.errors.append(pipeline_error)
        self.logger.error(
            "[%s] %s error in %s: %s",
            self.run_id[:8],
            pipeline_error.error_type,
            source,
            error,
        )

    def add_warning(self, message: str) -> None:
        """Record a non-blocking warning and log it."""
        self.warnings.append(message)
        self.logger.warning("[%s] %s", self.run_id[:8], message)

    # ------------------------------------------------------------------
    # Timing helpers
    # ------------------------------------------------------------------

    def start_timer(self, stage: str) -> None:
        """Start a wall-clock timer for the named stage."""
        self._active_timers[stage] = time.monotonic()

    def stop_timer(self, stage: str) -> None:
        """Stop the timer for the named stage and record elapsed time.

        Logs the elapsed time at INFO level.  Silently ignores
        stages that were never started (defensive programming).
        """
        start = self._active_timers.pop(stage, None)
        if start is not None:
            elapsed = time.monotonic() - start
            self.timing[stage] = elapsed
            self.logger.info(
                "[%s] Stage '%s' completed in %.3fs",
                self.run_id[:8],
                stage,
                elapsed,
            )

    # ------------------------------------------------------------------
    # Convenience properties
    # ------------------------------------------------------------------

    @property
    def source_priority(self) -> dict[str, int]:
        """Shortcut to the source-priority mapping from output config."""
        return self.output_config.source_priority

    @property
    def has_errors(self) -> bool:
        """Whether any errors were recorded during this run."""
        return len(self.errors) > 0
