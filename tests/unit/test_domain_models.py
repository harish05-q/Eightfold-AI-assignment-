"""Unit tests for domain models, enums, and exceptions.

Tests cover:
- Evidence creation, deterministic IDs, factory method, confidence bounds
- CanonicalCandidate construction (full and minimal)
- ProvenanceRecord immutability
- Enum values matching config/serialisation expectations
- Exception hierarchy and context propagation
- SourceDescriptor and InputManifest validation
"""

import pytest
from pydantic import ValidationError as PydanticValidationError

from candidate_transformer.domain.enums import (
    ExtractionMethod,
    MissingPolicy,
    SourceType,
)
from candidate_transformer.domain.exceptions import (
    CandidateTransformerError,
    ConfigurationError,
    ExtractionError,
    MergeConflictError,
    NormalizationError,
    ValidationError,
)
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
from candidate_transformer.domain.models.provenance import ProvenanceRecord


# ===================================================================
# Evidence tests
# ===================================================================


class TestEvidence:
    """Tests for the Evidence model."""

    def test_create_evidence_with_factory(self) -> None:
        """Factory method produces a valid Evidence with auto-computed ID."""
        evidence = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_1",
            field_name="full_name",
            raw_value="John Doe",
            confidence=0.8,
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        assert evidence.source_type == SourceType.RECRUITER_CSV
        assert evidence.source_ref == "test.csv"
        assert evidence.source_candidate_id == "row_1"
        assert evidence.field_name == "full_name"
        assert evidence.raw_value == "John Doe"
        assert evidence.confidence == 0.8
        assert evidence.extraction_method == ExtractionMethod.CSV_PARSE
        assert evidence.normalized_value is None
        assert len(evidence.evidence_id) == 16

    def test_deterministic_evidence_id(self) -> None:
        """Same inputs always produce the same evidence ID."""
        id_a = Evidence.build_id(
            SourceType.RECRUITER_CSV, "test.csv", "row_1", "full_name",
        )
        id_b = Evidence.build_id(
            SourceType.RECRUITER_CSV, "test.csv", "row_1", "full_name",
        )
        assert id_a == id_b

    def test_different_inputs_produce_different_ids(self) -> None:
        """Changing any attribute produces a different ID."""
        id_a = Evidence.build_id(
            SourceType.RECRUITER_CSV, "test.csv", "row_1", "full_name",
        )
        id_b = Evidence.build_id(
            SourceType.RECRUITER_CSV, "test.csv", "row_2", "full_name",
        )
        assert id_a != id_b

    def test_different_source_types_produce_different_ids(self) -> None:
        """Same field from different sources gets a different ID."""
        id_csv = Evidence.build_id(
            SourceType.RECRUITER_CSV, "test.csv", "row_1", "full_name",
        )
        id_github = Evidence.build_id(
            SourceType.GITHUB, "test.csv", "row_1", "full_name",
        )
        assert id_csv != id_github

    def test_confidence_lower_bound(self) -> None:
        """Confidence below 0.0 is rejected by pydantic validation."""
        with pytest.raises(PydanticValidationError):
            Evidence.create(
                source_type=SourceType.RECRUITER_CSV,
                source_ref="test.csv",
                source_candidate_id="row_1",
                field_name="full_name",
                raw_value="John Doe",
                confidence=-0.1,
                extraction_method=ExtractionMethod.CSV_PARSE,
            )

    def test_confidence_upper_bound(self) -> None:
        """Confidence above 1.0 is rejected by pydantic validation."""
        with pytest.raises(PydanticValidationError):
            Evidence.create(
                source_type=SourceType.RECRUITER_CSV,
                source_ref="test.csv",
                source_candidate_id="row_1",
                field_name="full_name",
                raw_value="John Doe",
                confidence=1.5,
                extraction_method=ExtractionMethod.CSV_PARSE,
            )

    def test_confidence_boundary_values(self) -> None:
        """Confidence at exactly 0.0 and 1.0 are accepted."""
        zero = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_1",
            field_name="full_name",
            raw_value="John Doe",
            confidence=0.0,
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        one = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_2",
            field_name="full_name",
            raw_value="Jane Doe",
            confidence=1.0,
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        assert zero.confidence == 0.0
        assert one.confidence == 1.0

    def test_default_confidence(self) -> None:
        """Default confidence is 0.5 when not explicitly specified."""
        evidence = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_1",
            field_name="full_name",
            raw_value="John Doe",
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        assert evidence.confidence == 0.5

    def test_normalized_value_can_be_set(self) -> None:
        """Evidence is mutable — normalizer can set normalized_value."""
        evidence = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_1",
            field_name="phone",
            raw_value="555-123-4567",
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        evidence.normalized_value = "+15551234567"
        assert evidence.normalized_value == "+15551234567"

    def test_timestamp_is_set_automatically(self) -> None:
        """Evidence gets a UTC timestamp on creation."""
        evidence = Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="test.csv",
            source_candidate_id="row_1",
            field_name="full_name",
            raw_value="John Doe",
            extraction_method=ExtractionMethod.CSV_PARSE,
        )
        assert evidence.timestamp is not None

    def test_raw_value_accepts_any_type(self) -> None:
        """raw_value can hold strings, dicts, lists, ints — anything."""
        for raw in ["text", 42, 3.14, ["a", "b"], {"key": "val"}, None]:
            ev = Evidence.create(
                source_type=SourceType.ATS_JSON,
                source_ref="ats.json",
                source_candidate_id="ats_1",
                field_name="misc",
                raw_value=raw,
                extraction_method=ExtractionMethod.JSON_PARSE,
            )
            assert ev.raw_value == raw


# ===================================================================
# CanonicalCandidate tests
# ===================================================================


class TestCanonicalCandidate:
    """Tests for the CanonicalCandidate and sub-models."""

    def test_minimal_candidate(self) -> None:
        """A candidate with only candidate_id is valid — all defaults apply."""
        candidate = CanonicalCandidate(candidate_id="test-123")
        assert candidate.candidate_id == "test-123"
        assert candidate.full_name is None
        assert candidate.emails == []
        assert candidate.phones == []
        assert candidate.location == Location()
        assert candidate.links == Links()
        assert candidate.headline is None
        assert candidate.years_experience is None
        assert candidate.skills == []
        assert candidate.experience == []
        assert candidate.education == []
        assert candidate.provenance == []
        assert candidate.overall_confidence == 0.0

    def test_full_candidate(self) -> None:
        """A fully populated candidate round-trips through construction."""
        candidate = CanonicalCandidate(
            candidate_id="test-456",
            full_name="Jane Smith",
            emails=["jane@example.com", "jsmith@corp.io"],
            phones=["+15551234567"],
            location=Location(city="San Francisco", region="CA", country="US"),
            links=Links(
                github="https://github.com/jsmith",
                linkedin="https://linkedin.com/in/jsmith",
                portfolio="https://jsmith.dev",
                other=["https://blog.jsmith.dev"],
            ),
            headline="Senior Engineer",
            years_experience=5.0,
            skills=[
                Skill(name="Python", confidence=0.9, sources=["github", "csv"]),
            ],
            experience=[
                Experience(
                    company="Acme",
                    title="Engineer",
                    start="2020-01",
                    end="2023-06",
                    summary="Built stuff",
                ),
            ],
            education=[
                Education(
                    institution="MIT",
                    degree="BS",
                    field="CS",
                    end_year=2019,
                ),
            ],
            provenance=[
                ProvenanceRecord(
                    field="full_name",
                    source="csv",
                    method="csv_parse",
                    confidence=0.9,
                ),
            ],
            overall_confidence=0.85,
        )
        assert candidate.full_name == "Jane Smith"
        assert len(candidate.emails) == 2
        assert candidate.location.country == "US"
        assert candidate.links.github == "https://github.com/jsmith"
        assert len(candidate.skills) == 1
        assert candidate.skills[0].name == "Python"
        assert candidate.experience[0].company == "Acme"
        assert candidate.education[0].end_year == 2019
        assert len(candidate.provenance) == 1
        assert candidate.overall_confidence == 0.85

    def test_candidate_model_dump(self) -> None:
        """model_dump produces a serialisable dictionary."""
        candidate = CanonicalCandidate(
            candidate_id="test-789",
            full_name="Bob",
            emails=["bob@example.com"],
        )
        data = candidate.model_dump()
        assert isinstance(data, dict)
        assert data["candidate_id"] == "test-789"
        assert data["full_name"] == "Bob"
        assert data["emails"] == ["bob@example.com"]
        assert data["overall_confidence"] == 0.0

    def test_location_defaults(self) -> None:
        """Default Location has all-None fields."""
        loc = Location()
        assert loc.city is None
        assert loc.region is None
        assert loc.country is None

    def test_links_defaults(self) -> None:
        """Default Links has None URLs and empty other list."""
        links = Links()
        assert links.linkedin is None
        assert links.github is None
        assert links.portfolio is None
        assert links.other == []

    def test_skill_requires_name(self) -> None:
        """Skill must have a name — omitting it raises a validation error."""
        with pytest.raises(PydanticValidationError):
            Skill(confidence=0.5)  # type: ignore[call-arg]

    def test_experience_requires_company_and_title(self) -> None:
        """Experience must have company and title."""
        exp = Experience(company="Acme", title="Engineer")
        assert exp.company == "Acme"
        assert exp.start is None
        with pytest.raises(PydanticValidationError):
            Experience(title="Engineer")  # type: ignore[call-arg]

    def test_education_requires_institution(self) -> None:
        """Education must have an institution."""
        edu = Education(institution="MIT")
        assert edu.degree is None
        with pytest.raises(PydanticValidationError):
            Education(degree="BS")  # type: ignore[call-arg]


# ===================================================================
# ProvenanceRecord tests
# ===================================================================


class TestProvenanceRecord:
    """Tests for ProvenanceRecord immutability and construction."""

    def test_creation(self) -> None:
        """ProvenanceRecord stores all four fields correctly."""
        prov = ProvenanceRecord(
            field="email",
            source="csv",
            method="csv_parse",
            confidence=0.9,
        )
        assert prov.field == "email"
        assert prov.source == "csv"
        assert prov.method == "csv_parse"
        assert prov.confidence == 0.9

    def test_immutability(self) -> None:
        """Frozen model — field assignment raises ValidationError."""
        prov = ProvenanceRecord(
            field="email", source="csv", method="csv_parse", confidence=0.9,
        )
        with pytest.raises(PydanticValidationError):
            prov.field = "phone"  # type: ignore[misc]

    def test_confidence_bounds(self) -> None:
        """Confidence outside [0.0, 1.0] is rejected."""
        with pytest.raises(PydanticValidationError):
            ProvenanceRecord(
                field="x", source="y", method="z", confidence=1.1,
            )
        with pytest.raises(PydanticValidationError):
            ProvenanceRecord(
                field="x", source="y", method="z", confidence=-0.1,
            )


# ===================================================================
# Enum tests
# ===================================================================


class TestEnums:
    """Tests for domain enumerations."""

    def test_source_type_values(self) -> None:
        """SourceType string values match configuration keys."""
        assert SourceType.RECRUITER_CSV.value == "csv"
        assert SourceType.ATS_JSON.value == "ats"
        assert SourceType.GITHUB.value == "github"
        assert SourceType.RESUME.value == "resume"

    def test_source_type_is_str(self) -> None:
        """SourceType inherits str — can be used as dict keys directly."""
        mapping: dict[str, int] = {SourceType.RECRUITER_CSV: 1}
        assert mapping["csv"] == 1

    def test_missing_policy_values(self) -> None:
        """MissingPolicy values match JSON config options."""
        assert MissingPolicy.NULL.value == "null"
        assert MissingPolicy.OMIT.value == "omit"
        assert MissingPolicy.ERROR.value == "error"

    def test_extraction_method_values(self) -> None:
        """ExtractionMethod values are all lower_snake_case strings."""
        for member in ExtractionMethod:
            assert member.value == member.value.lower()
            assert "_" in member.value  # all are compound names

    def test_all_source_types_have_unique_values(self) -> None:
        """No two SourceType members share the same value."""
        values = [e.value for e in SourceType]
        assert len(values) == len(set(values))


# ===================================================================
# Exception tests
# ===================================================================


class TestExceptions:
    """Tests for the domain exception hierarchy."""

    def test_hierarchy(self) -> None:
        """All domain exceptions inherit from CandidateTransformerError."""
        assert issubclass(ExtractionError, CandidateTransformerError)
        assert issubclass(NormalizationError, CandidateTransformerError)
        assert issubclass(MergeConflictError, CandidateTransformerError)
        assert issubclass(ValidationError, CandidateTransformerError)
        assert issubclass(ConfigurationError, CandidateTransformerError)

    def test_base_is_exception(self) -> None:
        """CandidateTransformerError is a standard Exception subclass."""
        assert issubclass(CandidateTransformerError, Exception)

    def test_exception_message(self) -> None:
        """Exception message is accessible via str()."""
        err = ExtractionError("Failed to parse CSV")
        assert str(err) == "Failed to parse CSV"

    def test_exception_with_context(self) -> None:
        """Context dict carries structured metadata for diagnostics."""
        err = ExtractionError(
            "Failed to parse CSV",
            context={"file": "test.csv", "line": 5},
        )
        assert err.context["file"] == "test.csv"
        assert err.context["line"] == 5

    def test_exception_default_context(self) -> None:
        """Context defaults to an empty dict when not provided."""
        err = NormalizationError("Phone parse failed")
        assert err.context == {}

    def test_exception_catchable_by_base(self) -> None:
        """Specific exceptions are catchable by CandidateTransformerError."""
        with pytest.raises(CandidateTransformerError):
            raise ConfigurationError("bad config")


# ===================================================================
# Input descriptor tests
# ===================================================================


class TestSourceDescriptor:
    """Tests for SourceDescriptor and InputManifest."""

    def test_source_descriptor_creation(self) -> None:
        """SourceDescriptor stores type, path, and priority."""
        desc = SourceDescriptor(
            source_type=SourceType.RECRUITER_CSV,
            path="data/recruiter.csv",
            priority=70,
        )
        assert desc.source_type == SourceType.RECRUITER_CSV
        assert desc.path == "data/recruiter.csv"
        assert desc.priority == 70

    def test_default_priority(self) -> None:
        """Default priority is 50."""
        desc = SourceDescriptor(
            source_type=SourceType.ATS_JSON,
            path="data/ats.json",
        )
        assert desc.priority == 50

    def test_priority_bounds(self) -> None:
        """Priority outside [0, 100] is rejected."""
        with pytest.raises(PydanticValidationError):
            SourceDescriptor(
                source_type=SourceType.ATS_JSON,
                path="data/ats.json",
                priority=101,
            )
        with pytest.raises(PydanticValidationError):
            SourceDescriptor(
                source_type=SourceType.ATS_JSON,
                path="data/ats.json",
                priority=-1,
            )

    def test_input_manifest_empty(self) -> None:
        """Empty manifest has no sources."""
        manifest = InputManifest()
        assert manifest.sources == []

    def test_input_manifest_with_sources(self) -> None:
        """Manifest holds a list of source descriptors."""
        manifest = InputManifest(
            sources=[
                SourceDescriptor(
                    source_type=SourceType.RECRUITER_CSV,
                    path="a.csv",
                ),
                SourceDescriptor(
                    source_type=SourceType.GITHUB,
                    path="https://github.com/user",
                    priority=80,
                ),
            ],
        )
        assert len(manifest.sources) == 2
        assert manifest.sources[1].priority == 80
