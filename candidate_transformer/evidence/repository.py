"""Evidence Repository layer.

The EvidenceRepository provides an in-memory store for all Evidence objects
extracted by the extraction layer. It offers efficient query capabilities 
(e.g., grouping by candidate ID or field name) to support the processors.
"""

from collections import defaultdict
import logging

from candidate_transformer.domain.models.evidence import Evidence


class EvidenceRepository:
    """In-memory data store for Evidence objects.

    Collects all evidence extracted across the pipeline and provides
    fast grouped lookups needed by processors (e.g. IdentityResolver,
    Merger).
    """

    def __init__(self) -> None:
        self._evidence: list[Evidence] = []
        self._by_source_candidate: dict[str, list[Evidence]] = defaultdict(list)
        self._logger = logging.getLogger("candidate_transformer.evidence.repository")

    def add(self, evidence: Evidence) -> None:
        """Add a single Evidence object to the repository."""
        self._evidence.append(evidence)
        self._by_source_candidate[evidence.source_candidate_id].append(evidence)

    def add_many(self, evidences: list[Evidence]) -> None:
        """Add multiple Evidence objects to the repository."""
        for ev in evidences:
            self.add(ev)

    def get_all(self) -> list[Evidence]:
        """Return all Evidence objects in the repository.
        
        Returns a copy to prevent accidental mutation of the internal list.
        """
        return list(self._evidence)

    def get_by_source_candidate_id(self, source_candidate_id: str) -> list[Evidence]:
        """Get all evidence associated with a specific source-level candidate ID."""
        return list(self._by_source_candidate.get(source_candidate_id, []))

    def get_all_source_candidate_ids(self) -> list[str]:
        """Return a list of all unique source_candidate_id values."""
        return list(self._by_source_candidate.keys())

    def get_grouped_by_field(
        self, source_candidate_id: str
    ) -> dict[str, list[Evidence]]:
        """Group a candidate's evidence by field name.

        Returns a dictionary mapping field_name to a list of Evidence objects
        for that field.
        """
        candidate_evidence = self.get_by_source_candidate_id(source_candidate_id)
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for ev in candidate_evidence:
            grouped[ev.field_name].append(ev)
        return dict(grouped)

    def clear(self) -> None:
        """Clear all stored evidence."""
        self._evidence.clear()
        self._by_source_candidate.clear()
        self._logger.debug("Evidence repository cleared")

    def __len__(self) -> int:
        return len(self._evidence)
