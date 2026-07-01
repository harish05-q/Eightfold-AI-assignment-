"""Shared test fixtures for the candidate transformer test suite.

These fixtures provide pre-built domain objects that are reused across
multiple test modules to avoid duplication and ensure consistency.
"""

import pytest

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
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
from candidate_transformer.config.models import OutputConfig
from candidate_transformer.pipeline.context import PipelineContext


# ---------------------------------------------------------------------------
# Pipeline context fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline_context() -> PipelineContext:
    """A minimal PipelineContext for unit-testing extractors/processors."""
    return PipelineContext(
        input_manifest=InputManifest(),
        output_config=OutputConfig(),
        run_id="test-run-000",
    )


# ---------------------------------------------------------------------------
# Evidence fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_evidence_name() -> Evidence:
    """Evidence for a full_name field from a CSV source."""
    return Evidence.create(
        source_type=SourceType.RECRUITER_CSV,
        source_ref="recruiter.csv",
        source_candidate_id="csv_row_1",
        field_name="full_name",
        raw_value="John Doe",
        confidence=0.8,
        extraction_method=ExtractionMethod.CSV_PARSE,
    )


@pytest.fixture
def sample_evidence_email() -> Evidence:
    """Evidence for an email field from a CSV source."""
    return Evidence.create(
        source_type=SourceType.RECRUITER_CSV,
        source_ref="recruiter.csv",
        source_candidate_id="csv_row_1",
        field_name="email",
        raw_value="john.doe@example.com",
        confidence=0.9,
        extraction_method=ExtractionMethod.CSV_PARSE,
    )


@pytest.fixture
def sample_evidence_phone() -> Evidence:
    """Evidence for a phone field from a CSV source."""
    return Evidence.create(
        source_type=SourceType.RECRUITER_CSV,
        source_ref="recruiter.csv",
        source_candidate_id="csv_row_1",
        field_name="phone",
        raw_value="(555) 123-4567",
        confidence=0.7,
        extraction_method=ExtractionMethod.CSV_PARSE,
    )


@pytest.fixture
def sample_github_evidence() -> Evidence:
    """Evidence for a full_name field from a GitHub source."""
    return Evidence.create(
        source_type=SourceType.GITHUB,
        source_ref="https://github.com/johndoe",
        source_candidate_id="github_johndoe",
        field_name="full_name",
        raw_value="John Doe",
        confidence=0.7,
        extraction_method=ExtractionMethod.API_FETCH,
    )


@pytest.fixture
def sample_resume_evidence() -> Evidence:
    """Evidence for a full_name field from a resume source."""
    return Evidence.create(
        source_type=SourceType.RESUME,
        source_ref="resume.pdf",
        source_candidate_id="resume_1",
        field_name="full_name",
        raw_value="John Doe",
        confidence=0.6,
        extraction_method=ExtractionMethod.PDF_PARSE,
    )


# ---------------------------------------------------------------------------
# Candidate fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_candidate() -> CanonicalCandidate:
    """A fully populated canonical candidate for integration-style tests."""
    return CanonicalCandidate(
        candidate_id="candidate-001",
        full_name="John Doe",
        emails=["john.doe@example.com"],
        phones=["+15551234567"],
        location=Location(city="San Francisco", region="CA", country="US"),
        links=Links(github="https://github.com/johndoe"),
        headline="Senior Software Engineer",
        years_experience=8.0,
        skills=[
            Skill(name="Python", confidence=0.9, sources=["github", "csv"]),
            Skill(name="JavaScript", confidence=0.7, sources=["github"]),
        ],
        experience=[
            Experience(
                company="TechCorp",
                title="Senior Engineer",
                start="2020-01",
                end="2024-06",
                summary="Led backend development",
            ),
        ],
        education=[
            Education(
                institution="MIT",
                degree="BS",
                field="Computer Science",
                end_year=2016,
            ),
        ],
        provenance=[
            ProvenanceRecord(
                field="full_name",
                source="csv",
                method="csv_parse",
                confidence=0.8,
            ),
            ProvenanceRecord(
                field="email",
                source="csv",
                method="csv_parse",
                confidence=0.9,
            ),
        ],
        overall_confidence=0.85,
    )


@pytest.fixture
def minimal_candidate() -> CanonicalCandidate:
    """A candidate with only a candidate_id — all other fields at defaults."""
    return CanonicalCandidate(candidate_id="candidate-empty")


# ---------------------------------------------------------------------------
# Input fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_manifest() -> InputManifest:
    """A manifest with one CSV and one GitHub source."""
    return InputManifest(
        sources=[
            SourceDescriptor(
                source_type=SourceType.RECRUITER_CSV,
                path="sample_inputs/recruiter.csv",
                priority=70,
            ),
            SourceDescriptor(
                source_type=SourceType.GITHUB,
                path="sample_inputs/github_profile.json",
                priority=80,
            ),
        ],
    )
