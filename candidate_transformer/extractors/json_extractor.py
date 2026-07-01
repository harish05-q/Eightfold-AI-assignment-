"""ATS JSON Extractor.

Extracts candidate profiles from semi-structured ATS JSON exports.
Handles mapping of various potential field names to canonical fields.
"""

import json
import logging
from pathlib import Path

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.pipeline.context import PipelineContext


class ATSJsonExtractor(BaseExtractor):
    """Concrete extractor for ATS JSON exports."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.ATS_JSON

    def extract(
        self,
        source: SourceDescriptor,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Extract evidence from an ATS JSON file."""
        json_path = Path(source.path)
        if not json_path.exists():
            raise ExtractionError(
                f"JSON file not found: {source.path}",
                context={"path": source.path},
            )

        evidences: list[Evidence] = []
        try:
            raw_text = json_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)

            # Ensure data is a list; if single object, wrap it
            records = data if isinstance(data, list) else [data]

            for record_idx, record in enumerate(records, start=1):
                # Try to find identifier
                email_val = self._get_first_key(record, ["email", "email_address", "contact_email"])
                phone_val = self._get_first_key(record, ["phone", "phone_number", "contact_phone", "mobile"])
                name_val = self._get_first_key(record, ["name", "candidate_name", "full_name"])

                # source candidate id construction
                if email_val and isinstance(email_val, str) and email_val.strip():
                    source_candidate_id = f"ats_cand_{email_val.strip().lower()}"
                elif phone_val and isinstance(phone_val, str) and phone_val.strip():
                    source_candidate_id = f"ats_cand_{phone_val.strip()}"
                elif name_val and isinstance(name_val, str) and name_val.strip():
                    source_candidate_id = f"ats_cand_{name_val.strip().lower().replace(' ', '_')}"
                else:
                    source_candidate_id = f"ats_cand_rec_{record_idx}"

                # Extract Name
                if name_val and isinstance(name_val, str) and name_val.strip():
                    evidences.append(
                        Evidence.create(
                            source_type=self.source_type,
                            source_ref=source.path,
                            source_candidate_id=source_candidate_id,
                            field_name="full_name",
                            raw_value=name_val.strip(),
                            confidence=0.85,
                            extraction_method=ExtractionMethod.JSON_PARSE,
                        )
                    )

                # Extract Emails
                emails = self._get_list_value(record, ["email", "email_address", "contact_email", "emails"])
                if emails:
                    evidences.append(
                        Evidence.create(
                            source_type=self.source_type,
                            source_ref=source.path,
                            source_candidate_id=source_candidate_id,
                            field_name="emails",
                            raw_value=emails,
                            confidence=0.9,
                            extraction_method=ExtractionMethod.JSON_PARSE,
                        )
                    )

                # Extract Phones
                phones = self._get_list_value(record, ["phone", "phone_number", "contact_phone", "mobile", "phones"])
                if phones:
                    evidences.append(
                        Evidence.create(
                            source_type=self.source_type,
                            source_ref=source.path,
                            source_candidate_id=source_candidate_id,
                            field_name="phones",
                            raw_value=phones,
                            confidence=0.85,
                            extraction_method=ExtractionMethod.JSON_PARSE,
                        )
                    )

                # Extract Location
                loc_city = self._get_first_key(record, ["city", "location_city"])
                loc_region = self._get_first_key(record, ["region", "state", "location_region"])
                loc_country = self._get_first_key(record, ["country", "location_country"])
                if loc_city or loc_region or loc_country:
                    location_dict = {
                        "city": str(loc_city).strip() if loc_city else None,
                        "region": str(loc_region).strip() if loc_region else None,
                        "country": str(loc_country).strip() if loc_country else None,
                    }
                    evidences.append(
                        Evidence.create(
                            source_type=self.source_type,
                            source_ref=source.path,
                            source_candidate_id=source_candidate_id,
                            field_name="location",
                            raw_value=location_dict,
                            confidence=0.8,
                            extraction_method=ExtractionMethod.JSON_PARSE,
                        )
                    )

                # Extract Headline
                headline = self._get_first_key(record, ["headline", "title", "job_title", "current_title"])
                if headline and isinstance(headline, str) and headline.strip():
                    evidences.append(
                        Evidence.create(
                            source_type=self.source_type,
                            source_ref=source.path,
                            source_candidate_id=source_candidate_id,
                            field_name="headline",
                            raw_value=headline.strip(),
                            confidence=0.8,
                            extraction_method=ExtractionMethod.JSON_PARSE,
                        )
                    )

                # Extract Years of Experience
                years_exp = self._get_first_key(record, ["years_experience", "experience_years", "yoe"])
                if years_exp is not None:
                    try:
                        yoe = float(years_exp)
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="years_experience",
                                raw_value=yoe,
                                confidence=0.8,
                                extraction_method=ExtractionMethod.JSON_PARSE,
                            )
                        )
                    except (ValueError, TypeError):
                        ctx.add_warning(f"Could not parse years_experience value '{years_exp}' in ATS JSON.")

                # Extract Skills
                skills = self._get_list_value(record, ["skills", "skills_list", "key_skills", "competencies"])
                if skills:
                    # Convert to Skill model format: list of dicts {name: ..., confidence: ...}
                    # ATS JSON skills are usually string names, so we map them to list of dicts with 1.0 confidence
                    raw_skills = []
                    for skill in skills:
                        if isinstance(skill, str) and skill.strip():
                            raw_skills.append({
                                "name": skill.strip(),
                                "confidence": 0.8, # confidence from this source
                                "sources": ["ats"],
                            })
                        elif isinstance(skill, dict) and "name" in skill:
                            raw_skills.append({
                                "name": str(skill["name"]).strip(),
                                "confidence": float(skill.get("confidence", 0.8)),
                                "sources": ["ats"],
                            })
                    if raw_skills:
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="skills",
                                raw_value=raw_skills,
                                confidence=0.85,
                                extraction_method=ExtractionMethod.JSON_PARSE,
                            )
                        )

                # Extract Experience
                exp_list = record.get("experience") or record.get("work_history") or record.get("employment_history")
                if exp_list and isinstance(exp_list, list):
                    raw_exp = []
                    for exp in exp_list:
                        if isinstance(exp, dict):
                            company = self._get_first_key(exp, ["company", "employer", "company_name"])
                            title = self._get_first_key(exp, ["title", "job_title", "position"])
                            start = self._get_first_key(exp, ["start", "start_date", "from"])
                            end = self._get_first_key(exp, ["end", "end_date", "to"])
                            summary = self._get_first_key(exp, ["summary", "description", "details"])

                            if company or title:
                                raw_exp.append({
                                    "company": str(company).strip() if company else "Unknown",
                                    "title": str(title).strip() if title else "Unknown",
                                    "start": str(start).strip() if start else None,
                                    "end": str(end).strip() if end else None,
                                    "summary": str(summary).strip() if summary else None,
                                })
                    if raw_exp:
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="experience",
                                raw_value=raw_exp,
                                confidence=0.85,
                                extraction_method=ExtractionMethod.JSON_PARSE,
                            )
                        )

                # Extract Education
                edu_list = record.get("education") or record.get("education_history") or record.get("academic_history")
                if edu_list and isinstance(edu_list, list):
                    raw_edu = []
                    for edu in edu_list:
                        if isinstance(edu, dict):
                            institution = self._get_first_key(edu, ["institution", "school", "university", "college"])
                            degree = self._get_first_key(edu, ["degree", "diploma", "certification"])
                            field = self._get_first_key(edu, ["field", "field_of_study", "major"])
                            end_year = self._get_first_key(edu, ["end_year", "graduation_year", "year"])

                            if institution:
                                parsed_year = None
                                if end_year is not None:
                                    try:
                                        parsed_year = int(end_year)
                                    except (ValueError, TypeError):
                                        pass
                                raw_edu.append({
                                    "institution": str(institution).strip(),
                                    "degree": str(degree).strip() if degree else None,
                                    "field": str(field).strip() if field else None,
                                    "end_year": parsed_year,
                                })
                    if raw_edu:
                        evidences.append(
                            Evidence.create(
                                source_type=self.source_type,
                                source_ref=source.path,
                                source_candidate_id=source_candidate_id,
                                field_name="education",
                                raw_value=raw_edu,
                                confidence=0.85,
                                extraction_method=ExtractionMethod.JSON_PARSE,
                            )
                        )

        except Exception as e:
            raise ExtractionError(
                f"Error reading ATS JSON file {source.path}: {str(e)}",
                context={"path": source.path, "error": str(e)},
            ) from e

        return evidences

    def _get_first_key(self, record: dict, keys: list[str]) -> object | None:
        """Find value of the first key in the list that exists in the record."""
        for key in keys:
            if key in record:
                return record[key]
        return None

    def _get_list_value(self, record: dict, keys: list[str]) -> list | None:
        """Extract a value and guarantee it is returned as a list or None."""
        val = self._get_first_key(record, keys)
        if val is None:
            return None
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            # Check if it's comma separated
            if "," in val:
                return [x.strip() for x in val.split(",") if x.strip()]
            return [val.strip()]
        return [val]
