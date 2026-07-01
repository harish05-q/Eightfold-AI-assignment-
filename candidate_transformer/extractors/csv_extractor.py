"""Recruiter CSV Extractor.

Extracts candidate profiles from structured CSV exports containing rows with columns:
name, email, phone, current_company, title.
"""

import csv
import logging
from pathlib import Path

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.pipeline.context import PipelineContext


class RecruiterCSVExtractor(BaseExtractor):
    """Concrete extractor for recruiter CSV exports."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.RECRUITER_CSV

    def extract(
        self,
        source: SourceDescriptor,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Extract evidence from a Recruiter CSV export file."""
        csv_path = Path(source.path)
        if not csv_path.exists():
            raise ExtractionError(
                f"CSV file not found: {source.path}",
                context={"path": source.path},
            )

        evidences: list[Evidence] = []
        try:
            with open(csv_path, mode="r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames:
                    ctx.add_warning(f"CSV file {source.path} has no headers or is empty.")
                    return []

                # Ensure expected headers or some overlapping headers exist
                headers = [h.strip().lower() for h in reader.fieldnames]
                ctx.logger.debug(
                    "CSV Headers: %s",
                    headers,
                )

                # Normalize headers mapping
                header_mapping = {h.strip().lower(): h for h in reader.fieldnames}

                # We map:
                # 'name' -> 'full_name'
                # 'email' -> 'emails' (or we parse it as individual values to be merged)
                # 'phone' -> 'phones'
                # 'current_company' -> 'experience' (as a part of experience or current experience)
                # 'title' -> 'headline' (or experience title)
                # Wait, the default schema has:
                # full_name (string)
                # emails (string[])
                # phones (string[])
                # location ({ city, region, country })
                # links ({ linkedin, github, portfolio, other[] })
                # headline (string | null)
                # years_experience (number | null)
                # skills ([ { name, confidence, sources[] } ])
                # experience ([ { company, title, start, end, summary } ])
                # education ([ { institution, degree, field, end_year } ])

                for row_idx, row in enumerate(reader, start=1):
                    # We need a unique per-row candidate identifier to group evidence from the same row
                    # Let's use email, phone or name if available in the row, or fallback to row index
                    email_val = row.get(header_mapping.get("email", ""))
                    phone_val = row.get(header_mapping.get("phone", ""))
                    name_val = row.get(header_mapping.get("name", ""))

                    # Construct unique source-specific candidate ID
                    # If we have email, use it as unique identifier to group evidence of this candidate.
                    # Otherwise, use name/phone, or row_idx
                    if email_val and email_val.strip():
                        source_candidate_id = f"csv_cand_{email_val.strip().lower()}"
                    elif phone_val and phone_val.strip():
                        source_candidate_id = f"csv_cand_{phone_val.strip()}"
                    elif name_val and name_val.strip():
                        source_candidate_id = f"csv_cand_{name_val.strip().lower().replace(' ', '_')}"
                    else:
                        source_candidate_id = f"csv_cand_row_{row_idx}"

                    # Extract name
                    if name_val and name_val.strip():
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="full_name",
                                raw_value=name_val.strip(),
                                confidence=0.8,
                                extraction_method=ExtractionMethod.CSV_PARSE,
                            )
                        )

                    # Extract email (can be list or single value, we'll extract as list/single raw string, the normalizer/merger will handle it)
                    if email_val and email_val.strip():
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="emails",
                                raw_value=[email_val.strip()],
                                confidence=0.9,
                                extraction_method=ExtractionMethod.CSV_PARSE,
                            )
                        )

                    # Extract phone
                    if phone_val and phone_val.strip():
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="phones",
                                raw_value=[phone_val.strip()],
                                confidence=0.8,
                                extraction_method=ExtractionMethod.CSV_PARSE,
                            )
                        )

                    # Extract title / headline
                    title_val = row.get(header_mapping.get("title", ""))
                    if title_val and title_val.strip():
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="headline",
                                raw_value=title_val.strip(),
                                confidence=0.7,
                                extraction_method=ExtractionMethod.CSV_PARSE,
                            )
                        )

                    # Extract current_company & title as a single Experience entry if both or either exists
                    company_val = row.get(header_mapping.get("current_company", ""))
                    if (company_val and company_val.strip()) or (title_val and title_val.strip()):
                        exp_entry = {
                            "company": company_val.strip() if company_val else "Unknown",
                            "title": title_val.strip() if title_val else "Unknown",
                            "start": None,
                            "end": None,
                            "summary": "Current position (extracted from CSV)",
                        }
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="experience",
                                raw_value=[exp_entry],
                                confidence=0.7,
                                extraction_method=ExtractionMethod.CSV_PARSE,
                            )
                        )

        except Exception as e:
            raise ExtractionError(
                f"Error reading CSV file {source.path}: {str(e)}",
                context={"path": source.path, "error": str(e)},
            ) from e

        return evidences
