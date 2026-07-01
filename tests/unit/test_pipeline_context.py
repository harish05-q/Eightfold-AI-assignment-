"""Unit tests for PipelineContext.

Tests cover:
- Creation with defaults and injected run_id
- Error recording and has_errors property
- Warning recording
- Timer start/stop and timing metrics
- Source priority delegation to OutputConfig
- Intermediate state (candidate_groups, candidates)
"""

import logging

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.candidate import CanonicalCandidate
from candidate_transformer.domain.models.input import InputManifest, SourceDescriptor
from candidate_transformer.domain.enums import SourceType
from candidate_transformer.pipeline.context import PipelineContext, PipelineError


def _make_context(
    run_id: str = "test-run-001",
    source_priority: dict[str, int] | None = None,
) -> PipelineContext:
    """Helper to build a PipelineContext with sensible test defaults."""
    manifest = InputManifest(
        sources=[
            SourceDescriptor(
                source_type=SourceType.RECRUITER_CSV,
                path="test.csv",
            ),
        ],
    )
    priority = source_priority or {"csv": 70, "ats": 100}
    config = OutputConfig(source_priority=priority)
    logger = logging.getLogger("test_pipeline_context")
    logger.setLevel(logging.DEBUG)
    return PipelineContext(
        input_manifest=manifest,
        output_config=config,
        logger=logger,
        run_id=run_id,
    )


class TestPipelineContextCreation:
    """Tests for PipelineContext initialisation."""

    def test_fixed_run_id(self) -> None:
        """Injected run_id is used instead of a generated UUID."""
        ctx = _make_context(run_id="fixed-id")
        assert ctx.run_id == "fixed-id"

    def test_default_run_id_is_uuid(self) -> None:
        """When run_id is not provided, a UUID is generated."""
        manifest = InputManifest()
        config = OutputConfig()
        ctx = PipelineContext(input_manifest=manifest, output_config=config)
        assert len(ctx.run_id) == 36  # UUID format: 8-4-4-4-12

    def test_initial_state(self) -> None:
        """Fresh context has empty errors, warnings, timing, and results."""
        ctx = _make_context()
        assert ctx.errors == []
        assert ctx.warnings == []
        assert ctx.timing == {}
        assert ctx.candidate_groups == {}
        assert ctx.candidates == []
        assert ctx.has_errors is False


class TestPipelineContextErrors:
    """Tests for error recording."""

    def test_add_error(self) -> None:
        """add_error stores a PipelineError with correct fields."""
        ctx = _make_context()
        exc = ValueError("something broke")
        ctx.add_error(stage="extraction", source="csv_extractor", error=exc)

        assert len(ctx.errors) == 1
        err = ctx.errors[0]
        assert isinstance(err, PipelineError)
        assert err.stage == "extraction"
        assert err.source == "csv_extractor"
        assert err.error_type == "ValueError"
        assert err.message == "something broke"
        assert err.timestamp is not None

    def test_multiple_errors(self) -> None:
        """Multiple errors accumulate in order."""
        ctx = _make_context()
        ctx.add_error("extraction", "csv", RuntimeError("err1"))
        ctx.add_error("normalisation", "phone", TypeError("err2"))
        assert len(ctx.errors) == 2
        assert ctx.errors[0].stage == "extraction"
        assert ctx.errors[1].stage == "normalisation"

    def test_has_errors_true(self) -> None:
        """has_errors is True after an error is recorded."""
        ctx = _make_context()
        ctx.add_error("test", "test", Exception("x"))
        assert ctx.has_errors is True

    def test_has_errors_false(self) -> None:
        """has_errors is False when no errors have been recorded."""
        ctx = _make_context()
        assert ctx.has_errors is False


class TestPipelineContextWarnings:
    """Tests for warning recording."""

    def test_add_warning(self) -> None:
        """add_warning stores the message string."""
        ctx = _make_context()
        ctx.add_warning("Phone parse failed for +1-invalid")
        assert len(ctx.warnings) == 1
        assert ctx.warnings[0] == "Phone parse failed for +1-invalid"

    def test_multiple_warnings(self) -> None:
        """Warnings accumulate in order."""
        ctx = _make_context()
        ctx.add_warning("warn1")
        ctx.add_warning("warn2")
        assert ctx.warnings == ["warn1", "warn2"]


class TestPipelineContextTimers:
    """Tests for timing instrumentation."""

    def test_start_stop_records_elapsed(self) -> None:
        """stop_timer records a positive elapsed time."""
        ctx = _make_context()
        ctx.start_timer("extraction")
        # Simulate some work (timer uses monotonic clock)
        ctx.stop_timer("extraction")
        assert "extraction" in ctx.timing
        assert ctx.timing["extraction"] >= 0.0

    def test_stop_without_start_is_safe(self) -> None:
        """Stopping a never-started timer does not raise."""
        ctx = _make_context()
        ctx.stop_timer("nonexistent")
        assert "nonexistent" not in ctx.timing

    def test_multiple_stages(self) -> None:
        """Multiple stages can be timed independently."""
        ctx = _make_context()
        ctx.start_timer("extraction")
        ctx.stop_timer("extraction")
        ctx.start_timer("normalisation")
        ctx.stop_timer("normalisation")
        assert "extraction" in ctx.timing
        assert "normalisation" in ctx.timing


class TestPipelineContextSourcePriority:
    """Tests for source priority delegation."""

    def test_source_priority_delegates(self) -> None:
        """source_priority property returns output_config's mapping."""
        ctx = _make_context(source_priority={"ats": 50, "csv": 100})
        assert ctx.source_priority == {"ats": 50, "csv": 100}

    def test_source_priority_matches_config(self) -> None:
        """The context and config return the same priority mapping."""
        ctx = _make_context()
        assert ctx.source_priority is ctx.output_config.source_priority


class TestPipelineContextIntermediateState:
    """Tests for intermediate results set by processors."""

    def test_candidate_groups_mutable(self) -> None:
        """Processors can write candidate groups to the context."""
        ctx = _make_context()
        ctx.candidate_groups["candidate-001"] = ["csv_row_1", "github_john"]
        assert len(ctx.candidate_groups) == 1
        assert "csv_row_1" in ctx.candidate_groups["candidate-001"]

    def test_candidates_mutable(self) -> None:
        """Processors can append canonical candidates to the context."""
        ctx = _make_context()
        candidate = CanonicalCandidate(candidate_id="test-001")
        ctx.candidates.append(candidate)
        assert len(ctx.candidates) == 1
        assert ctx.candidates[0].candidate_id == "test-001"
