"""Unit tests for ConfigValidator."""

import pytest

from candidate_transformer.config.models import OutputConfig, FieldSpec
from candidate_transformer.validation.validator import ConfigValidator


class TestConfigValidator:
    """Tests for ConfigValidator."""

    def test_default_config_valid_data(self) -> None:
        validator = ConfigValidator()
        config = OutputConfig(include_confidence=True)
        data = {
            "candidate_id": "cand_1",
            "full_name": "Alice",
            "emails": ["alice@example.com"],
            "phones": [],
            "location": {"city": "Paris"},
            "links": {},
            "headline": "Engineer",
            "years_experience": 5.0,
            "skills": [{"name": "Python"}],
            "experience": [],
            "education": [],
            "provenance": [],
            "overall_confidence": 0.9,
        }
        
        result = validator.validate(data, config)
        assert result.is_valid
        assert not result.errors
        assert not result.warnings

    def test_default_config_missing_required(self) -> None:
        validator = ConfigValidator()
        config = OutputConfig()
        # Missing candidate_id which is required by default
        data = {
            "full_name": "Alice",
            "emails": []
        }
        
        result = validator.validate(data, config)
        assert not result.is_valid
        assert any("candidate_id" in err for err in result.errors)

    def test_type_checking(self) -> None:
        validator = ConfigValidator()
        config = OutputConfig(
            fields=[
                FieldSpec(path="name", type="string"),
                FieldSpec(path="age", type="number"),
                FieldSpec(path="flags", type="string[]"),
                FieldSpec(path="details", type="object"),
                FieldSpec(path="items", type="object[]"),
            ]
        )
        data = {
            "name": 123,  # Should be string
            "age": "25",  # Should be number
            "flags": ["a", 2],  # Contains non-string
            "details": [],  # Should be object/dict
            "items": [{}, "not dict"],  # Contains non-object
        }
        
        result = validator.validate(data, config)
        assert not result.is_valid
        assert len(result.errors) == 5
        assert "expected string, got int" in result.errors[0]
        assert "expected number, got str" in result.errors[1]
        assert "contains non-string items" in result.errors[2]
        assert "expected object, got list" in result.errors[3]
        assert "contains non-object items" in result.errors[4]

    def test_extraneous_fields_produce_warnings(self) -> None:
        validator = ConfigValidator()
        config = OutputConfig(
            fields=[
                FieldSpec(path="name", type="string")
            ]
        )
        data = {
            "name": "Alice",
            "extra_field": 123
        }
        
        result = validator.validate(data, config)
        assert result.is_valid  # Still valid, just warnings
        assert len(result.warnings) == 1
        assert "Extraneous field" in result.warnings[0]
        assert "extra_field" in result.warnings[0]

    def test_unknown_type_produces_warning(self) -> None:
        validator = ConfigValidator()
        config = OutputConfig(
            fields=[
                FieldSpec(path="name", type="magic")
            ]
        )
        data = {
            "name": "Alice",
        }
        
        result = validator.validate(data, config)
        assert result.is_valid
        assert len(result.warnings) == 1
        assert "Unknown type 'magic'" in result.warnings[0]
