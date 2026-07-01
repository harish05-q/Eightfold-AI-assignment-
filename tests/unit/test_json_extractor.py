"""Unit tests for ATSJsonExtractor."""

import json
from pathlib import Path
import pytest

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.extractors.json_extractor import ATSJsonExtractor
from candidate_transformer.pipeline.context import PipelineContext


class TestJSONExtractor:
    """Tests for ATSJsonExtractor."""

    def test_source_type(self) -> None:
        """Extractor reports correct source type."""
        extractor = ATSJsonExtractor()
        assert extractor.source_type == SourceType.ATS_JSON

    def test_extract_valid_json(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Valid ATS JSON candidate record extracts all expected fields."""
        ats_record = {
            "candidate_name": "Jane Smith",
            "contact_email": "jane@example.com",
            "contact_phone": "555-987-6543",
            "location_city": "New York",
            "location_country": "USA",
            "job_title": "Product Manager",
            "experience_years": 6.5,
            "key_skills": ["Agile", "Roadmapping", "Python"],
            "employment_history": [
                {
                    "company_name": "Startup Inc",
                    "position": "Associate PM",
                    "start_date": "2019-01",
                    "end_date": "2021-12",
                    "description": "Managed mobile app launch"
                }
            ],
            "academic_history": [
                {
                    "school": "NYU",
                    "degree": "MBA",
                    "graduation_year": 2018
                }
            ]
        }
        json_file = tmp_path / "ats_export.json"
        json_file.write_text(json.dumps(ats_record), encoding="utf-8")

        extractor = ATSJsonExtractor()
        source = SourceDescriptor(source_type=SourceType.ATS_JSON, path=str(json_file))
        evidences = extractor.extract(source, pipeline_context)

        fields = {e.field_name: e for e in evidences}
        assert "full_name" in fields
        assert "emails" in fields
        assert "phones" in fields
        assert "location" in fields
        assert "headline" in fields
        assert "years_experience" in fields
        assert "skills" in fields
        assert "experience" in fields
        assert "education" in fields

        assert fields["full_name"].raw_value == "Jane Smith"
        assert fields["emails"].raw_value == ["jane@example.com"]
        assert fields["phones"].raw_value == ["555-987-6543"]
        assert fields["location"].raw_value == {"city": "New York", "region": None, "country": "USA"}
        assert fields["headline"].raw_value == "Product Manager"
        assert fields["years_experience"].raw_value == 6.5
        assert len(fields["skills"].raw_value) == 3
        assert fields["experience"].raw_value[0]["company"] == "Startup Inc"
        assert fields["education"].raw_value[0]["institution"] == "NYU"
        assert fields["education"].raw_value[0]["end_year"] == 2018

    def test_extract_missing_file_raises(self, pipeline_context: PipelineContext) -> None:
        """Extracting non-existent JSON file raises ExtractionError."""
        extractor = ATSJsonExtractor()
        source = SourceDescriptor(source_type=SourceType.ATS_JSON, path="nonexistent_ats.json")
        with pytest.raises(ExtractionError, match="JSON file not found"):
            extractor.extract(source, pipeline_context)

    def test_extract_malformed_json_raises(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Malformed JSON file raises ExtractionError."""
        json_file = tmp_path / "bad.json"
        json_file.write_text("{invalid json", encoding="utf-8")

        extractor = ATSJsonExtractor()
        source = SourceDescriptor(source_type=SourceType.ATS_JSON, path=str(json_file))
        with pytest.raises(ExtractionError, match="Error reading ATS JSON file"):
            extractor.extract(source, pipeline_context)
