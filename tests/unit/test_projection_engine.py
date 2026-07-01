"""Unit tests for ProjectionEngine."""

from pathlib import Path
import pytest
import json

from candidate_transformer.config.models import OutputConfig, FieldSpec
from candidate_transformer.domain.enums import MissingPolicy
from candidate_transformer.domain.exceptions import ValidationError
from candidate_transformer.domain.models.candidate import (
    CanonicalCandidate,
    Location,
    Links,
    Skill,
    Experience,
)
from candidate_transformer.projection.engine import ProjectionEngine


class TestProjectionEngine:
    """Tests for ProjectionEngine."""

    @pytest.fixture
    def sample_candidate(self) -> CanonicalCandidate:
        return CanonicalCandidate(
            candidate_id="cand_12345",
            full_name="Alice Smith",
            emails=["alice@example.com", "alice.smith@example.org"],
            phones=["+1 (555) 019-2834"],
            location=Location(city="San Francisco", region="CA", country="US"),
            links=Links(linkedin="linkedin.com/in/alice", github="github.com/alice"),
            headline="Staff Engineer",
            years_experience=8.5,
            skills=[
                Skill(name="Python", confidence=0.95, sources=["github"]),
                Skill(name="React.js", confidence=0.85, sources=["resume"]),
            ],
            experience=[
                Experience(company="Google", title="Software Engineer", start="2020-01", end="2023-01"),
            ]
        )

    def test_default_projection(self, sample_candidate: CanonicalCandidate) -> None:
        """Default projection maps all default attributes and respects include_confidence."""
        engine = ProjectionEngine()
        config = OutputConfig(include_confidence=True)
        
        projected = engine.project(sample_candidate, config)
        
        assert projected["candidate_id"] == "cand_12345"
        assert projected["full_name"] == "Alice Smith"
        assert projected["emails"] == ["alice@example.com", "alice.smith@example.org"]
        assert projected["location"]["city"] == "San Francisco"
        assert projected["skills"][0]["name"] == "Python"
        assert projected["skills"][0]["confidence"] == 0.95
        assert projected["overall_confidence"] == 0.0

    def test_default_projection_exclude_confidence(self, sample_candidate: CanonicalCandidate) -> None:
        """Setting include_confidence=False removes confidence keys."""
        engine = ProjectionEngine()
        config = OutputConfig(include_confidence=False)
        
        projected = engine.project(sample_candidate, config)
        
        assert "overall_confidence" not in projected
        assert "confidence" not in projected["skills"][0]
        assert projected["skills"][0]["name"] == "Python"

    def test_custom_fields_mapping(self, sample_candidate: CanonicalCandidate) -> None:
        """Can project a subset of fields and rename them using custom specs."""
        engine = ProjectionEngine()
        config = OutputConfig(
            fields=[
                FieldSpec(path="name", alias="from", **{"from": "full_name"}),
                FieldSpec(path="primary_email", alias="from", **{"from": "emails[0]"}),
                FieldSpec(path="city", alias="from", **{"from": "location.city"}),
                FieldSpec(path="skill_names", alias="from", **{"from": "skills[].name"}),
            ]
        )
        
        projected = engine.project(sample_candidate, config)
        
        assert len(projected) == 4
        assert projected["name"] == "Alice Smith"
        assert projected["primary_email"] == "alice@example.com"
        assert projected["city"] == "San Francisco"
        assert projected["skill_names"] == ["Python", "React.js"]

    def test_required_field_missing_raises(self, sample_candidate: CanonicalCandidate) -> None:
        """Required field missing should raise ValidationError."""
        engine = ProjectionEngine()
        # candidate years_experience is float, let's request something missing
        sample_candidate.headline = None
        
        config = OutputConfig(
            fields=[
                FieldSpec(path="headline", required=True)
            ]
        )
        
        with pytest.raises(ValidationError) as excinfo:
            engine.project(sample_candidate, config)
        assert "Required field" in str(excinfo.value)

    def test_global_missing_policy_omit(self, sample_candidate: CanonicalCandidate) -> None:
        """MissingPolicy.OMIT strips missing fields from output dictionary."""
        engine = ProjectionEngine()
        sample_candidate.headline = None
        
        config = OutputConfig(
            on_missing=MissingPolicy.OMIT,
            fields=[
                FieldSpec(path="full_name"),
                FieldSpec(path="headline")
            ]
        )
        
        projected = engine.project(sample_candidate, config)
        assert "full_name" in projected
        assert "headline" not in projected

    def test_global_missing_policy_error(self, sample_candidate: CanonicalCandidate) -> None:
        """MissingPolicy.ERROR raises ValidationError when any field is missing."""
        engine = ProjectionEngine()
        sample_candidate.headline = None
        
        config = OutputConfig(
            on_missing=MissingPolicy.ERROR,
            fields=[
                FieldSpec(path="headline")
            ]
        )
        
        with pytest.raises(ValidationError):
            engine.project(sample_candidate, config)

    def test_field_level_normalization(self, sample_candidate: CanonicalCandidate, tmp_path: Path) -> None:
        """E164 phone normalisation and canonical skill mapping work during projection."""
        # Setup skill aliases
        aliases_file = tmp_path / "skill_aliases.json"
        aliases_file.write_text(json.dumps({"react.js": "React"}), encoding="utf-8")
        
        engine = ProjectionEngine(aliases_path=aliases_file)
        
        sample_candidate.phones = ["555.123.4567"]
        
        config = OutputConfig(
            fields=[
                FieldSpec(path="phones", normalize="E164"),
                FieldSpec(path="skill_names", alias="from", **{"from": "skills[].name"}, normalize="canonical")
            ]
        )
        
        projected = engine.project(sample_candidate, config)
        assert projected["phones"] == ["5551234567"]
        assert projected["skill_names"] == ["Python", "React"]  # React.js got mapped to React
