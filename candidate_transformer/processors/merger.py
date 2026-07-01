"""Evidence Merger Processor.

Produces CanonicalCandidate objects for each candidate group by selecting
or aggregating field values based on Source Priority and Confidence.
"""

from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.domain.models.candidate import (
    CanonicalCandidate,
    Location,
    Links,
    Experience,
    Education,
    Skill,
)
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext


class EvidenceMerger(BaseProcessor):
    """Merges grouped Evidence into unified CanonicalCandidate objects."""

    @property
    def name(self) -> str:
        return "EvidenceMerger"

    @property
    def order(self) -> int:
        return 40  # Runs after IdentityResolver

    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        """Merge all candidate groups into CanonicalCandidate records."""
        if not ctx.candidate_groups:
            ctx.logger.warning("No candidate groups found to merge.")
            return

        for unified_id, source_ids in ctx.candidate_groups.items():
            # Collect all evidence for this unified identity
            all_evidence: list[Evidence] = []
            for sid in source_ids:
                all_evidence.extend(repo.get_by_source_candidate_id(sid))

            # Group all evidence by field
            field_evidence: dict[str, list[Evidence]] = {}
            for ev in all_evidence:
                field_evidence.setdefault(ev.field_name, []).append(ev)

            # Build the canonical candidate
            try:
                candidate = self._merge_candidate(unified_id, field_evidence, ctx)
                ctx.candidates.append(candidate)
            except Exception as e:
                ctx.add_error(
                    stage="merging",
                    source="EvidenceMerger",
                    error=e,
                )

    def _merge_candidate(
        self, unified_id: str, field_evidence: dict[str, list[Evidence]], ctx: PipelineContext
    ) -> CanonicalCandidate:
        """Construct a CanonicalCandidate from grouped evidence."""
        return CanonicalCandidate(
            candidate_id=unified_id,
            full_name=self._pick_best_scalar(field_evidence.get("full_name", []), ctx),
            emails=self._merge_lists(field_evidence.get("emails", []), ctx),
            phones=self._merge_lists(field_evidence.get("phones", []), ctx),
            location=self._merge_location(field_evidence.get("location", []), ctx),
            links=self._merge_links(field_evidence.get("links", []), ctx),
            headline=self._pick_best_scalar(field_evidence.get("headline", []), ctx),
            years_experience=self._pick_best_scalar(field_evidence.get("years_experience", []), ctx),
            skills=self._merge_skills(field_evidence.get("skills", []), ctx),
            experience=self._merge_experience(field_evidence.get("experience", []), ctx),
            education=self._merge_education(field_evidence.get("education", []), ctx),
        )

    def _get_score(self, ev: Evidence, ctx: PipelineContext) -> float:
        """Calculate a composite score based on source priority and confidence.
        
        Priority (0-100) dominates. Confidence (0.0-1.0) is a tie-breaker.
        Score = priority + confidence.
        """
        priority = ctx.source_priority.get(ev.source_type.value, 0)
        return float(priority) + float(ev.confidence)

    def _pick_best_scalar(self, evidences: list[Evidence], ctx: PipelineContext) -> any:
        """Pick the single best value for scalar fields (string, int, float) based on score."""
        if not evidences:
            return None

        # Sort descending by score, and pick the first valid one
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if val is not None and val != "":
                return val
        return None

    def _merge_lists(self, evidences: list[Evidence], ctx: PipelineContext) -> list[str]:
        """Merge lists of strings (emails, phones), deduplicating values."""
        merged_set = set()
        merged_list = []
        
        # Sort descending to favor high-priority items at the front of the list
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(val, list):
                for item in val:
                    if item and item not in merged_set:
                        merged_set.add(item)
                        merged_list.append(str(item))
        return merged_list

    def _merge_location(self, evidences: list[Evidence], ctx: PipelineContext) -> Location:
        """Merge location objects by picking the best available fields independently."""
        city, region, country = None, None, None
        
        # Sort descending so higher priority sources get evaluated first
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(val, dict):
                if city is None and val.get("city"):
                    city = val["city"]
                if region is None and val.get("region"):
                    region = val["region"]
                if country is None and val.get("country"):
                    country = val["country"]
                    
        return Location(city=city, region=region, country=country)

    def _merge_links(self, evidences: list[Evidence], ctx: PipelineContext) -> Links:
        """Merge link dictionaries independently."""
        linkedin, github, portfolio = None, None, None
        other_set = set()
        other_list = []
        
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(val, dict):
                if linkedin is None and val.get("linkedin"):
                    linkedin = val["linkedin"]
                if github is None and val.get("github"):
                    github = val["github"]
                if portfolio is None and val.get("portfolio"):
                    portfolio = val["portfolio"]
                if val.get("other"):
                    for url in val["other"]:
                        if url not in other_set:
                            other_set.add(url)
                            other_list.append(url)
                            
        return Links(linkedin=linkedin, github=github, portfolio=portfolio, other=other_list)

    def _merge_skills(self, evidences: list[Evidence], ctx: PipelineContext) -> list[Skill]:
        """Aggregate skills, accumulating sources and averaging confidence for duplicates."""
        skill_map: dict[str, dict] = {}
        
        for ev in evidences:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if not isinstance(val, list):
                continue
                
            for skill_dict in val:
                if not isinstance(skill_dict, dict) or "name" not in skill_dict:
                    continue
                    
                name = str(skill_dict["name"]).strip()
                # Use lowercase for case-insensitive deduplication, but preserve original case
                lookup = name.lower()
                
                conf = float(skill_dict.get("confidence", ev.confidence))
                sources = skill_dict.get("sources", [ev.source_type.value])
                
                if lookup in skill_map:
                    # Accumulate
                    existing = skill_map[lookup]
                    existing["confidences"].append(conf)
                    for src in sources:
                        if src not in existing["sources"]:
                            existing["sources"].append(src)
                else:
                    skill_map[lookup] = {
                        "name": name,
                        "confidences": [conf],
                        "sources": list(sources)
                    }
                    
        # Construct Skill models
        skills = []
        for v in skill_map.values():
            avg_conf = sum(v["confidences"]) / len(v["confidences"])
            skills.append(
                Skill(
                    name=v["name"],
                    confidence=round(avg_conf, 2),
                    sources=v["sources"]
                )
            )
            
        # Sort skills by confidence descending
        return sorted(skills, key=lambda s: s.confidence, reverse=True)

    def _merge_experience(self, evidences: list[Evidence], ctx: PipelineContext) -> list[Experience]:
        """Merge experience arrays, avoiding exact duplicates."""
        # A simple deduplication based on company + title combination
        exp_map = {}
        
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if not isinstance(val, list):
                continue
                
            for e_dict in val:
                if not isinstance(e_dict, dict) or "company" not in e_dict or "title" not in e_dict:
                    continue
                
                company = str(e_dict["company"]).strip()
                title = str(e_dict["title"]).strip()
                key = f"{company.lower()}::{title.lower()}"
                
                if key not in exp_map:
                    exp_map[key] = Experience(
                        company=company,
                        title=title,
                        start=e_dict.get("start"),
                        end=e_dict.get("end"),
                        summary=e_dict.get("summary"),
                    )
        
        return list(exp_map.values())

    def _merge_education(self, evidences: list[Evidence], ctx: PipelineContext) -> list[Education]:
        """Merge education arrays, avoiding exact duplicates."""
        edu_map = {}
        
        sorted_ev = sorted(evidences, key=lambda e: self._get_score(e, ctx), reverse=True)
        for ev in sorted_ev:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if not isinstance(val, list):
                continue
                
            for e_dict in val:
                if not isinstance(e_dict, dict) or "institution" not in e_dict:
                    continue
                
                institution = str(e_dict["institution"]).strip()
                degree = str(e_dict.get("degree", "")).strip()
                field = str(e_dict.get("field", "")).strip()
                
                key = f"{institution.lower()}::{degree.lower()}::{field.lower()}"
                
                if key not in edu_map:
                    try:
                        end_year = int(e_dict["end_year"]) if e_dict.get("end_year") else None
                    except (ValueError, TypeError):
                        end_year = None
                        
                    edu_map[key] = Education(
                        institution=institution,
                        degree=degree if degree else None,
                        field=field if field else None,
                        end_year=end_year,
                    )
        
        return list(edu_map.values())
