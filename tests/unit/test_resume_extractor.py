"""Unit tests for ResumeExtractor."""

from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.extractors.resume_extractor import ResumeExtractor
from candidate_transformer.pipeline.context import PipelineContext


class TestResumeExtractor:
    """Tests for ResumeExtractor."""

    def test_source_type(self) -> None:
        """Extractor reports correct source type."""
        extractor = ResumeExtractor()
        assert extractor.source_type == SourceType.RESUME

    def test_extract_txt_resume(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Valid text resume parses name, email, phone, and skills correctly."""
        txt_content = """Alice Cooper
Senior Engineer

Email: alice@example.com
Phone: +1 (555) 345-6789

Skills: Python, Go, Kubernetes, Docker, Git

Experience:
Worked at TechCorp.
"""
        txt_file = tmp_path / "resume.txt"
        txt_file.write_text(txt_content, encoding="utf-8")

        extractor = ResumeExtractor()
        source = SourceDescriptor(source_type=SourceType.RESUME, path=str(txt_file))
        evidences = extractor.extract(source, pipeline_context)

        fields = {e.field_name: e for e in evidences}
        assert "full_name" in fields
        assert "emails" in fields
        assert "phones" in fields
        assert "skills" in fields

        assert fields["full_name"].raw_value == "Alice Cooper"
        assert fields["emails"].raw_value == ["alice@example.com"]
        assert fields["phones"].raw_value == ["+1 (555) 345-6789"]

        # Check skills
        skills = fields["skills"].raw_value
        assert len(skills) == 5
        skill_names = [s["name"] for s in skills]
        assert "Python" in skill_names
        assert "Go" in skill_names
        assert "Kubernetes" in skill_names

    @patch("pdfplumber.open")
    def test_extract_pdf_resume_mocked(self, mock_pdf_open: MagicMock, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Mocked PDF reader extracts text and triggers heuristic parsing."""
        # Setup mock PDF structure
        mock_pdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = """Bob Builder
Backend Lead

Email: bob@example.com
Phone: (555) 987-1234
Skills: FastAPI, SQL
"""
        mock_pdf.pages = [mock_page]
        mock_pdf_open.return_value.__enter__.return_value = mock_pdf

        # Create dummy PDF file (doesn't need real PDF content since we patched open)
        pdf_file = tmp_path / "resume.pdf"
        pdf_file.write_text("dummy pdf contents", encoding="utf-8")

        extractor = ResumeExtractor()
        source = SourceDescriptor(source_type=SourceType.RESUME, path=str(pdf_file))
        evidences = extractor.extract(source, pipeline_context)

        fields = {e.field_name: e for e in evidences}
        assert "full_name" in fields
        assert "emails" in fields
        assert "phones" in fields
        assert "skills" in fields

        assert fields["full_name"].raw_value == "Bob Builder"
        assert fields["emails"].raw_value == ["bob@example.com"]
        assert fields["phones"].raw_value == ["(555) 987-1234"]
        
        skills = fields["skills"].raw_value
        skill_names = [s["name"] for s in skills]
        assert "FastAPI" in skill_names
        assert "SQL" in skill_names

    def test_extract_missing_file_raises(self, pipeline_context: PipelineContext) -> None:
        """Missing resume file raises ExtractionError."""
        extractor = ResumeExtractor()
        source = SourceDescriptor(source_type=SourceType.RESUME, path="nonexistent_resume.pdf")
        with pytest.raises(ExtractionError, match="Resume file not found"):
            extractor.extract(source, pipeline_context)

    def test_unsupported_file_type_raises(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Unsupported extension raises ExtractionError."""
        bad_file = tmp_path / "resume.docx"
        bad_file.write_text("dummy content", encoding="utf-8")

        extractor = ResumeExtractor()
        source = SourceDescriptor(source_type=SourceType.RESUME, path=str(bad_file))
        with pytest.raises(ExtractionError, match="Unsupported resume file type"):
            extractor.extract(source, pipeline_context)
