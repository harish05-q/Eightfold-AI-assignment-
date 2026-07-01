"""Field Normalizer Processor.

Normalizes extracted Evidence values:
- Emails: lowercased, whitespace trimmed.
- Phones: strips non-numeric characters (except leading +), handles E.164-like formatting.
- Strings: trimmed whitespace.
"""

from typing import Any
import re

from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext


class FieldNormalizer(BaseProcessor):
    """Normalizes raw values within Evidence objects."""

    @property
    def name(self) -> str:
        return "FieldNormalizer"

    @property
    def order(self) -> int:
        return 10  # First processor

    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        """Iterate over all evidence and populate normalized_value."""
        for ev in repo.get_all():
            try:
                if ev.field_name == "emails":
                    ev.normalized_value = self._normalize_emails(ev.raw_value)
                elif ev.field_name == "phones":
                    ev.normalized_value = self._normalize_phones(ev.raw_value)
                elif ev.field_name == "full_name":
                    ev.normalized_value = self._normalize_string(ev.raw_value)
                elif ev.field_name == "headline":
                    ev.normalized_value = self._normalize_string(ev.raw_value)
                elif ev.field_name == "location":
                    ev.normalized_value = self._normalize_location(ev.raw_value)
                else:
                    # Pass-through for other types, or they remain None
                    # to indicate no special normalization occurred.
                    ev.normalized_value = ev.raw_value
            except Exception as e:
                ctx.add_warning(
                    f"Failed to normalize {ev.field_name} for candidate {ev.source_candidate_id}: {e}"
                )
                ev.normalized_value = ev.raw_value

    def _normalize_string(self, value: Any) -> Any:
        """Trim whitespace from string."""
        if isinstance(value, str):
            return value.strip()
        return value

    def _normalize_emails(self, value: Any) -> list[str]:
        """Lowercase and trim emails."""
        if not isinstance(value, list):
            return value
        return [str(e).strip().lower() for e in value if e]

    def _normalize_phones(self, value: Any) -> list[str]:
        """Convert phones to E.164 standard format using phonenumbers.
        
        Falls back to stripping non-digits if parsing fails.
        """
        import phonenumbers
        
        if not isinstance(value, list):
            return value
        
        normalized = []
        for p in value:
            if not p:
                continue
            p_str = str(p).strip()
            
            try:
                # Default region to US if missing country code
                parsed = phonenumbers.parse(p_str, "US")
                if phonenumbers.is_valid_number(parsed):
                    formatted = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                    normalized.append(formatted)
                    continue
            except phonenumbers.NumberParseException:
                pass
                
            # Fallback for unparseable or invalid numbers
            has_plus = p_str.startswith('+')
            digits = re.sub(r"\D", "", p_str)
            if digits:
                normalized.append(f"+{digits}" if has_plus else digits)
                
        return normalized

    def _normalize_location(self, value: Any) -> dict[str, str | None]:
        """Trim whitespace in location dict fields."""
        if not isinstance(value, dict):
            return value
        
        return {
            "city": self._normalize_string(value.get("city")),
            "region": self._normalize_string(value.get("region")),
            "country": self._normalize_string(value.get("country")),
        }
