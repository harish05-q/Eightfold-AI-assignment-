"""Unit tests for RecruiterCSVExtractor."""

from pathlib import Path
import pytest

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.extractors.csv_extractor import RecruiterCSVExtractor
from candidate_transformer.pipeline.context import PipelineContext


class TestCSVExtractor:
    """Tests for RecruiterCSVExtractor."""

    def test_source_type(self) -> None:
        """Extractor reports correct source type."""
        extractor = RecruiterCSVExtractor()
        assert extractor.source_type == SourceType.RECRUITER_CSV

    def test_extract_valid_csv(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Valid CSV row extracts all expected candidate evidence."""
        csv_content = "name,email,phone,current_company,title\nJohn Doe,john@example.com,555-123-4567,Google,Senior Engineer\n"
        csv_file = tmp_path / "recruiter.csv"
        csv_file.write_text(csv_content, encoding="utf-8")

        extractor = RecruiterCSVExtractor()
        source = SourceDescriptor(source_type=SourceType.RECRUITER_CSV, path=str(csv_file))
        evidences = extractor.extract(source, pipeline_context)

        # Expected field names: full_name, emails, phones, headline, experience
        fields = [e.field_name for e in evidences]
        assert "full_name" in fields
        assert "emails" in fields
        assert "phones" in fields
        assert "headline" in fields
        assert "experience" in fields

        # Check values
        name_ev = next(e for e in evidences if e.field_name == "full_name")
        assert name_ev.raw_value == "John Doe"
        assert name_ev.source_candidate_id == "csv_cand_john@example.com"

        email_ev = next(e for e in evidences if e.field_name == "emails")
        assert email_ev.raw_value == ["john@example.com"]

        phone_ev = next(e for e in evidences if e.field_name == "phones")
        assert phone_ev.raw_value == ["555-123-4567"]

    def test_extract_missing_file_raises(self, pipeline_context: PipelineContext) -> None:
        """Extracting non-existent file raises ExtractionError."""
        extractor = RecruiterCSVExtractor()
        source = SourceDescriptor(source_type=SourceType.RECRUITER_CSV, path="nonexistent_recruiter.csv")
        with pytest.raises(ExtractionError, match="CSV file not found"):
            extractor.extract(source, pipeline_context)

    def test_extract_empty_csv(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Empty CSV file produces no evidence and logs a warning."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("", encoding="utf-8")

        extractor = RecruiterCSVExtractor()
        source = SourceDescriptor(source_type=SourceType.RECRUITER_CSV, path=str(csv_file))
        evidences = extractor.extract(source, pipeline_context)

        assert evidences == []
        assert len(pipeline_context.warnings) > 0
        assert "has no headers or is empty" in pipeline_context.warnings[0]
