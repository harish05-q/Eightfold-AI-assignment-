"""Resume Extractor.

Supports plain text (.txt) and PDF (.pdf) resumes.
Extracts candidate info using deterministic text parsing rules and heuristics:
- First non-empty line is assumed to be the candidate name.
- Email and phone are extracted via regex patterns.
"""

import logging
from pathlib import Path
import re

import pdfplumber

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.pipeline.context import PipelineContext


class ResumeExtractor(BaseExtractor):
    """Concrete extractor for Resume PDF/TXT files."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.RESUME

    def extract(
        self,
        source: SourceDescriptor,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Extract evidence from a Resume PDF or TXT file."""
        resume_path = Path(source.path)
        if not resume_path.exists():
            raise ExtractionError(
                f"Resume file not found: {source.path}",
                context={"path": source.path},
            )

        # Determine file extension and extract raw text
        ext = resume_path.suffix.lower()
        if ext == ".pdf":
            ctx.logger.info("Parsing PDF resume: %s", source.path)
            raw_text = self._extract_text_from_pdf(resume_path, ctx)
            method = ExtractionMethod.PDF_PARSE
        elif ext in (".txt", ".text", ""):
            ctx.logger.info("Parsing TXT resume: %s", source.path)
            raw_text = self._extract_text_from_txt(resume_path, ctx)
            method = ExtractionMethod.TEXT_PARSE
        else:
            raise ExtractionError(
                f"Unsupported resume file type: {ext} in {source.path}",
                context={"path": source.path, "extension": ext},
            )

        if not raw_text or not raw_text.strip():
            ctx.add_warning(f"Resume file '{source.path}' is empty or contains no extractable text.")
            return []

        # Parse candidate information from text using deterministic heuristics
        evidences = self._parse_resume_text(raw_text, source.path, method, ctx)
        return evidences

    def _extract_text_from_pdf(self, path: Path, ctx: PipelineContext) -> str:
        """Extract text from a PDF using pdfplumber."""
        text_parts = []
        try:
            with pdfplumber.open(path) as pdf:
                for idx, page in enumerate(pdf.pages, start=1):
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                    else:
                        ctx.add_warning(f"PDF Page {idx} in '{path}' contains no extractable text (possibly scanned image).")
            return "\n".join(text_parts)
        except Exception as e:
            raise ExtractionError(
                f"Failed to parse PDF resume {path}: {str(e)}",
                context={"path": str(path), "error": str(e)},
            ) from e

    def _extract_text_from_txt(self, path: Path, ctx: PipelineContext) -> str:
        """Extract text from a plain text file."""
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            raise ExtractionError(
                f"Failed to read TXT resume {path}: {str(e)}",
                context={"path": str(path), "error": str(e)},
            ) from e

    def _parse_resume_text(
        self,
        text: str,
        source_ref: str,
        method: ExtractionMethod,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Apply deterministic heuristics to extract candidate name, email, phone, skills, experience."""
        evidences: list[Evidence] = []
        lines = [line.strip() for line in text.splitlines()]
        non_empty_lines = [line for line in lines if line]

        if not non_empty_lines:
            return []

        # Heuristic 1: First non-empty line is assumed to be the candidate's full name
        name_val = non_empty_lines[0]
        # Quick validation: check if name is too long or contains symbols (indicates it's not a name)
        if len(name_val) < 50 and not re.search(r"[:{}@\[\]]", name_val):
            source_candidate_id = f"resume_cand_{name_val.lower().replace(' ', '_')}"
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source_ref,
                    source_candidate_id=source_candidate_id,
                    field_name="full_name",
                    raw_value=name_val,
                    confidence=0.7,  # heuristic has lower confidence
                    extraction_method=method,
                )
            )
        else:
            source_candidate_id = "resume_cand_unknown"

        # Heuristic 2: Extract email using regex
        # Standard regex pattern for email addresses
        email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
        emails = re.findall(email_pattern, text)
        if emails:
            # deduplicate
            unique_emails = list(dict.fromkeys(emails))
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source_ref,
                    source_candidate_id=source_candidate_id,
                    field_name="emails",
                    raw_value=unique_emails,
                    confidence=0.9,
                    extraction_method=method,
                )
            )
            # If name was unknown, update source_candidate_id to use email if available
            if source_candidate_id == "resume_cand_unknown":
                source_candidate_id = f"resume_cand_{unique_emails[0].lower()}"
                # Update any already appended evidence
                for ev in evidences:
                    ev.source_candidate_id = source_candidate_id

        # Heuristic 3: Extract phone using regex
        # Pattern matching common phone formats like +1-555-123-4567, (555) 123-4567, etc.
        phone_pattern = r"(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
        phones = re.findall(phone_pattern, text)
        if phones:
            unique_phones = list(dict.fromkeys(phones))
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source_ref,
                    source_candidate_id=source_candidate_id,
                    field_name="phones",
                    raw_value=unique_phones,
                    confidence=0.8,
                    extraction_method=method,
                )
            )

        # Heuristic 4: Extract skills from a section or by keyword lookup
        # Let's check for a "Skills" section or lines starting with "Skills:"
        skills_found = []
        in_skills_section = False
        skills_header_pattern = re.compile(r"^(skills|technologies|technical skills|languages):", re.IGNORECASE)

        for line in lines:
            if skills_header_pattern.match(line):
                # Extract value in this line after colon
                parts = line.split(":", 1)
                if len(parts) > 1 and parts[1].strip():
                    skills_found.extend([s.strip() for s in parts[1].split(",") if s.strip()])
                in_skills_section = True
                continue
            # If in section, extract skills until empty line or another section
            if in_skills_section:
                if not line:
                    in_skills_section = False
                elif ":" in line and any(keyword in line.lower() for keyword in ["experience", "education", "employment"]):
                    in_skills_section = False
                else:
                    skills_found.extend([s.strip() for s in line.split(",") if s.strip()])

        # If no explicit section found, look for keyword matches in text
        if not skills_found:
            # Common programming skills/languages for simple keyword matching
            common_skills = ["Python", "Java", "C++", "JavaScript", "HTML", "CSS", "SQL", "Docker", "Git", "FastAPI"]
            for skill in common_skills:
                if re.search(r"\b" + re.escape(skill) + r"\b", text, re.IGNORECASE):
                    skills_found.append(skill)

        if skills_found:
            skills_payload = [
                {
                    "name": s,
                    "confidence": 0.7,
                    "sources": ["resume"],
                }
                for s in list(dict.fromkeys(skills_found))
            ]
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source_ref,
                    source_candidate_id=source_candidate_id,
                    field_name="skills",
                    raw_value=skills_payload,
                    confidence=0.75,
                    extraction_method=method,
                )
            )

        return evidences
