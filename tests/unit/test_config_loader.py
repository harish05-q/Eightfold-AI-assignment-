"""Unit tests for configuration models and the ConfigLoader.

Tests cover:
- FieldSpec defaults, alias handling ("from" → from_path), resolved_from
- OutputConfig defaults, custom source_priority, get_priority
- ConfigLoader: default config, custom file, missing file, invalid JSON,
  invalid structure, load_from_dict
"""

import json
from pathlib import Path

import pytest

from candidate_transformer.config.loader import ConfigLoader
from candidate_transformer.config.models import FieldSpec, OutputConfig
from candidate_transformer.domain.enums import MissingPolicy
from candidate_transformer.domain.exceptions import ConfigurationError


# ===================================================================
# FieldSpec tests
# ===================================================================


class TestFieldSpec:
    """Tests for the FieldSpec configuration model."""

    def test_defaults(self) -> None:
        """FieldSpec with only path set uses sensible defaults."""
        spec = FieldSpec(path="full_name")
        assert spec.path == "full_name"
        assert spec.from_path is None
        assert spec.type == "string"
        assert spec.required is False
        assert spec.normalize is None

    def test_resolved_from_defaults_to_path(self) -> None:
        """resolved_from returns path when from_path is None."""
        spec = FieldSpec(path="full_name")
        assert spec.resolved_from == "full_name"

    def test_resolved_from_uses_from_path(self) -> None:
        """resolved_from returns from_path when explicitly set."""
        spec = FieldSpec(path="primary_email", from_path="emails[0]")
        assert spec.resolved_from == "emails[0]"

    def test_from_alias_in_json(self) -> None:
        """JSON key 'from' maps to from_path via Pydantic alias."""
        raw = {"path": "phone", "from": "phones[0]", "type": "string"}
        spec = FieldSpec.model_validate(raw)
        assert spec.from_path == "phones[0]"
        assert spec.resolved_from == "phones[0]"

    def test_from_path_via_python_name(self) -> None:
        """Python name 'from_path' works via populate_by_name."""
        spec = FieldSpec(path="phone", from_path="phones[0]")
        assert spec.from_path == "phones[0]"

    def test_full_spec(self) -> None:
        """Fully populated FieldSpec round-trips correctly."""
        spec = FieldSpec(
            path="skills",
            from_path="skills[].name",
            type="string[]",
            required=True,
            normalize="canonical",
        )
        assert spec.path == "skills"
        assert spec.from_path == "skills[].name"
        assert spec.type == "string[]"
        assert spec.required is True
        assert spec.normalize == "canonical"

    def test_model_dump_uses_python_names(self) -> None:
        """model_dump() uses Python attribute names by default."""
        spec = FieldSpec(path="x", from_path="y")
        data = spec.model_dump()
        assert "from_path" in data
        assert "from" not in data

    def test_model_dump_by_alias(self) -> None:
        """model_dump(by_alias=True) uses the 'from' alias."""
        spec = FieldSpec(path="x", from_path="y")
        data = spec.model_dump(by_alias=True)
        assert "from" in data
        assert "from_path" not in data


# ===================================================================
# OutputConfig tests
# ===================================================================


class TestOutputConfig:
    """Tests for the OutputConfig configuration model."""

    def test_defaults(self) -> None:
        """Default OutputConfig has empty fields and standard priorities."""
        config = OutputConfig()
        assert config.fields == []
        assert config.include_confidence is True
        assert config.on_missing == MissingPolicy.NULL
        assert config.source_priority == {
            "ats": 100,
            "resume": 90,
            "github": 80,
            "csv": 70,
        }

    def test_custom_source_priority(self) -> None:
        """Source priority is fully configurable."""
        config = OutputConfig(source_priority={"ats": 50, "csv": 100})
        assert config.source_priority["csv"] == 100
        assert config.source_priority["ats"] == 50

    def test_get_priority_known_source(self) -> None:
        """get_priority returns the configured weight for known sources."""
        config = OutputConfig()
        assert config.get_priority("ats") == 100
        assert config.get_priority("csv") == 70

    def test_get_priority_unknown_source(self) -> None:
        """get_priority returns 0 for unrecognised source types."""
        config = OutputConfig()
        assert config.get_priority("unknown_source") == 0

    def test_on_missing_from_string(self) -> None:
        """on_missing accepts string values and converts to enum."""
        config = OutputConfig.model_validate({"on_missing": "omit"})
        assert config.on_missing == MissingPolicy.OMIT

    def test_on_missing_error(self) -> None:
        """on_missing='error' parses correctly."""
        config = OutputConfig.model_validate({"on_missing": "error"})
        assert config.on_missing == MissingPolicy.ERROR

    def test_with_field_specs(self) -> None:
        """OutputConfig with explicit field specs."""
        raw = {
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {"path": "primary_email", "from": "emails[0]", "type": "string"},
            ],
            "include_confidence": False,
            "on_missing": "omit",
        }
        config = OutputConfig.model_validate(raw)
        assert len(config.fields) == 2
        assert config.fields[0].path == "full_name"
        assert config.fields[0].required is True
        assert config.fields[1].from_path == "emails[0]"
        assert config.include_confidence is False
        assert config.on_missing == MissingPolicy.OMIT

    def test_full_assignment_example(self) -> None:
        """The assignment's example config parses without error."""
        raw = {
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {
                    "path": "primary_email",
                    "from": "emails[0]",
                    "type": "string",
                    "required": True,
                },
                {
                    "path": "phone",
                    "from": "phones[0]",
                    "type": "string",
                    "normalize": "E164",
                },
                {
                    "path": "skills",
                    "from": "skills[].name",
                    "type": "string[]",
                    "normalize": "canonical",
                },
            ],
            "include_confidence": True,
            "on_missing": "null",
        }
        config = OutputConfig.model_validate(raw)
        assert len(config.fields) == 4
        assert config.fields[2].normalize == "E164"
        assert config.fields[3].resolved_from == "skills[].name"


# ===================================================================
# ConfigLoader tests
# ===================================================================


class TestConfigLoader:
    """Tests for the ConfigLoader."""

    def test_load_default(self) -> None:
        """load_default() returns a valid config with all 13 fields."""
        loader = ConfigLoader()
        config = loader.load_default()
        assert isinstance(config, OutputConfig)
        assert len(config.fields) == 13
        assert config.on_missing == MissingPolicy.NULL
        assert config.include_confidence is True

    def test_load_none_returns_default(self) -> None:
        """load(None) delegates to load_default()."""
        loader = ConfigLoader()
        config = loader.load(None)
        assert len(config.fields) == 13

    def test_load_default_field_paths(self) -> None:
        """Default config field paths match canonical model attributes."""
        loader = ConfigLoader()
        config = loader.load_default()
        paths = [f.path for f in config.fields]
        expected = [
            "candidate_id", "full_name", "emails", "phones",
            "location", "links", "headline", "years_experience",
            "skills", "experience", "education", "provenance",
            "overall_confidence",
        ]
        assert paths == expected

    def test_load_default_source_priority(self) -> None:
        """Default config has the agreed source priorities."""
        loader = ConfigLoader()
        config = loader.load_default()
        assert config.source_priority == {
            "ats": 100,
            "resume": 90,
            "github": 80,
            "csv": 70,
        }

    def test_load_custom_file(self, tmp_path: Path) -> None:
        """load() reads and validates a custom JSON config."""
        custom = {
            "fields": [
                {"path": "full_name", "type": "string", "required": True},
                {"path": "email", "from": "emails[0]", "type": "string"},
            ],
            "include_confidence": False,
            "on_missing": "omit",
            "source_priority": {"ats": 50, "csv": 100},
        }
        config_file = tmp_path / "custom.json"
        config_file.write_text(json.dumps(custom), encoding="utf-8")

        loader = ConfigLoader()
        config = loader.load(str(config_file))
        assert len(config.fields) == 2
        assert config.include_confidence is False
        assert config.on_missing == MissingPolicy.OMIT
        assert config.source_priority["csv"] == 100

    def test_load_missing_file_raises(self) -> None:
        """load() raises ConfigurationError for non-existent files."""
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="not found"):
            loader.load("/nonexistent/config.json")

    def test_load_invalid_json_raises(self, tmp_path: Path) -> None:
        """load() raises ConfigurationError for malformed JSON."""
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json", encoding="utf-8")

        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="Invalid JSON"):
            loader.load(str(bad_file))

    def test_load_non_object_json_raises(self, tmp_path: Path) -> None:
        """load() raises ConfigurationError when JSON root is not an object."""
        array_file = tmp_path / "array.json"
        array_file.write_text("[1, 2, 3]", encoding="utf-8")

        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="JSON object"):
            loader.load(str(array_file))

    def test_load_invalid_structure_raises(self, tmp_path: Path) -> None:
        """load() raises ConfigurationError for invalid field types."""
        bad_structure = {"fields": "not_a_list"}
        config_file = tmp_path / "bad_structure.json"
        config_file.write_text(json.dumps(bad_structure), encoding="utf-8")

        loader = ConfigLoader()
        with pytest.raises(ConfigurationError, match="Invalid configuration"):
            loader.load(str(config_file))

    def test_load_from_dict(self) -> None:
        """load_from_dict() validates a raw dictionary directly."""
        loader = ConfigLoader()
        raw = {
            "fields": [{"path": "full_name", "required": True}],
            "on_missing": "null",
        }
        config = loader.load_from_dict(raw)
        assert len(config.fields) == 1
        assert config.fields[0].required is True

    def test_load_from_dict_invalid_raises(self) -> None:
        """load_from_dict() raises ConfigurationError on invalid input."""
        loader = ConfigLoader()
        with pytest.raises(ConfigurationError):
            loader.load_from_dict({"on_missing": "invalid_policy"})

    def test_load_empty_config(self, tmp_path: Path) -> None:
        """An empty JSON object yields an OutputConfig with all defaults."""
        config_file = tmp_path / "empty.json"
        config_file.write_text("{}", encoding="utf-8")

        loader = ConfigLoader()
        config = loader.load(str(config_file))
        assert config.fields == []
        assert config.on_missing == MissingPolicy.NULL
        assert config.include_confidence is True

    def test_load_partial_config(self, tmp_path: Path) -> None:
        """A config with only source_priority uses defaults for the rest."""
        partial = {"source_priority": {"ats": 200, "github": 10}}
        config_file = tmp_path / "partial.json"
        config_file.write_text(json.dumps(partial), encoding="utf-8")

        loader = ConfigLoader()
        config = loader.load(str(config_file))
        assert config.source_priority["ats"] == 200
        assert config.source_priority["github"] == 10
        assert config.on_missing == MissingPolicy.NULL
