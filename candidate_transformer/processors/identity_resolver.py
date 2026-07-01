"""Identity Resolver Processor.

Groups Evidence belonging to the same individual candidate across
different data sources using deterministic matching logic.

Matching priority:
1. Exact email match
2. Exact phone match
3. Exact name match (case-insensitive)

Output is stored in `ctx.candidate_groups`.
"""

from collections import defaultdict
import uuid

from candidate_transformer.domain.interfaces.processor import BaseProcessor
from candidate_transformer.evidence.repository import EvidenceRepository
from candidate_transformer.pipeline.context import PipelineContext


class IdentityResolver(BaseProcessor):
    """Resolves identities across multiple sources using deterministic keys."""

    @property
    def name(self) -> str:
        return "IdentityResolver"

    @property
    def order(self) -> int:
        return 30  # Runs after SkillCanonicalizer

    def process(self, repo: EvidenceRepository, ctx: PipelineContext) -> None:
        """Group source_candidate_ids that belong to the same person."""
        # Maps for exact matching (value -> unified_candidate_id)
        email_to_uid: dict[str, str] = {}
        phone_to_uid: dict[str, str] = {}
        name_to_uid: dict[str, str] = {}

        # The output mapping: unified_candidate_id -> set of source_candidate_ids
        uid_to_sources: dict[str, set[str]] = defaultdict(set)

        # To ensure deterministic iteration, process candidate IDs sorted alphabetically
        sorted_candidate_ids = sorted(repo.get_all_source_candidate_ids())

        # Build graph of connections
        # Nodes can be source IDs or attribute strings (e.g., "email:x@y.com")
        adj: dict[str, set[str]] = defaultdict(set)

        for source_id in sorted_candidate_ids:
            grouped = repo.get_grouped_by_field(source_id)
            emails = self._extract_list(grouped.get("emails", []))
            phones = self._extract_list(grouped.get("phones", []))
            names = self._extract_strings(grouped.get("full_name", []))

            # Connect source_id to its attributes
            for email in emails:
                node = f"email:{email}"
                adj[source_id].add(node)
                adj[node].add(source_id)
            for phone in phones:
                node = f"phone:{phone}"
                adj[source_id].add(node)
                adj[node].add(source_id)
            for name in names:
                node = f"name:{name}"
                adj[source_id].add(node)
                adj[node].add(source_id)

        # Find connected components of source IDs
        visited = set()
        components = []

        for source_id in sorted_candidate_ids:
            if source_id not in visited:
                # BFS
                comp_sources = []
                queue = [source_id]
                visited.add(source_id)
                
                while queue:
                    curr = queue.pop(0)
                    if not curr.startswith("email:") and not curr.startswith("phone:") and not curr.startswith("name:"):
                        comp_sources.append(curr)
                        
                    for neighbor in sorted(adj[curr]):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                            
                components.append(sorted(comp_sources))

        # Assign deterministic unified IDs
        for comp in components:
            # Deterministic ID based on the first sorted source ID in the component
            first_source = comp[0]
            # Use a short hash of the first source ID to be stable across runs
            import hashlib
            stable_hash = hashlib.md5(first_source.encode()).hexdigest()[:12]
            unified_id = f"cand_{stable_hash}"
            ctx.candidate_groups[unified_id] = comp

        ctx.logger.info("IdentityResolver merged %d source IDs into %d unified candidates.",
                        len(sorted_candidate_ids), len(components))

    def _extract_list(self, evidences: list) -> set[str]:
        """Extract strings from lists inside Evidence objects."""
        values = set()
        for ev in evidences:
            val_list = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(val_list, list):
                for v in val_list:
                    if isinstance(v, str) and v.strip():
                        values.add(v.strip().lower())
        return values

    def _extract_strings(self, evidences: list) -> set[str]:
        """Extract single strings inside Evidence objects."""
        values = set()
        for ev in evidences:
            val = ev.normalized_value if ev.normalized_value is not None else ev.raw_value
            if isinstance(val, str) and val.strip():
                values.add(val.strip().lower())
        return values
