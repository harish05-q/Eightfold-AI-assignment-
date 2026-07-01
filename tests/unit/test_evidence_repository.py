"""Unit tests for EvidenceRepository."""

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.evidence.repository import EvidenceRepository


class TestEvidenceRepository:
    """Tests for EvidenceRepository."""

    def _create_dummy_evidence(
        self,
        candidate_id: str,
        field_name: str,
        value: str,
    ) -> Evidence:
        """Helper to create Evidence objects for testing."""
        return Evidence.create(
            source_type=SourceType.RECRUITER_CSV,
            source_ref="dummy.csv",
            source_candidate_id=candidate_id,
            field_name=field_name,
            raw_value=value,
            confidence=1.0,
            extraction_method=ExtractionMethod.CSV_PARSE,
        )

    def test_add_and_len(self) -> None:
        """Test adding evidence and repository length."""
        repo = EvidenceRepository()
        assert len(repo) == 0

        ev = self._create_dummy_evidence("c1", "full_name", "Alice")
        repo.add(ev)
        assert len(repo) == 1

    def test_add_many(self) -> None:
        """Test adding multiple evidence objects."""
        repo = EvidenceRepository()
        evs = [
            self._create_dummy_evidence("c1", "full_name", "Alice"),
            self._create_dummy_evidence("c2", "full_name", "Bob"),
        ]
        repo.add_many(evs)
        assert len(repo) == 2

    def test_get_all(self) -> None:
        """Test retrieving all evidence, ensuring list copy is returned."""
        repo = EvidenceRepository()
        ev = self._create_dummy_evidence("c1", "full_name", "Alice")
        repo.add(ev)
        
        all_ev = repo.get_all()
        assert len(all_ev) == 1
        assert all_ev[0].source_candidate_id == "c1"
        
        # Mutating the returned list shouldn't affect the repository
        all_ev.append(self._create_dummy_evidence("c2", "full_name", "Bob"))
        assert len(repo) == 1

    def test_get_by_source_candidate_id(self) -> None:
        """Test retrieving evidence filtered by candidate ID."""
        repo = EvidenceRepository()
        ev1 = self._create_dummy_evidence("c1", "full_name", "Alice")
        ev2 = self._create_dummy_evidence("c1", "emails", "alice@example.com")
        ev3 = self._create_dummy_evidence("c2", "full_name", "Bob")
        
        repo.add_many([ev1, ev2, ev3])
        
        c1_ev = repo.get_by_source_candidate_id("c1")
        assert len(c1_ev) == 2
        assert all(e.source_candidate_id == "c1" for e in c1_ev)
        
        c3_ev = repo.get_by_source_candidate_id("c3")
        assert len(c3_ev) == 0

    def test_get_all_source_candidate_ids(self) -> None:
        """Test retrieving unique candidate IDs."""
        repo = EvidenceRepository()
        repo.add(self._create_dummy_evidence("c1", "full_name", "Alice"))
        repo.add(self._create_dummy_evidence("c1", "emails", "alice@example.com"))
        repo.add(self._create_dummy_evidence("c2", "full_name", "Bob"))
        
        ids = repo.get_all_source_candidate_ids()
        assert len(ids) == 2
        assert set(ids) == {"c1", "c2"}

    def test_get_grouped_by_field(self) -> None:
        """Test grouping a candidate's evidence by field name."""
        repo = EvidenceRepository()
        repo.add(self._create_dummy_evidence("c1", "full_name", "Alice"))
        repo.add(self._create_dummy_evidence("c1", "emails", "alice1@example.com"))
        repo.add(self._create_dummy_evidence("c1", "emails", "alice2@example.com"))
        
        grouped = repo.get_grouped_by_field("c1")
        assert "full_name" in grouped
        assert len(grouped["full_name"]) == 1
        
        assert "emails" in grouped
        assert len(grouped["emails"]) == 2
        
        assert "phones" not in grouped

    def test_clear(self) -> None:
        """Test clearing the repository."""
        repo = EvidenceRepository()
        repo.add(self._create_dummy_evidence("c1", "full_name", "Alice"))
        assert len(repo) == 1
        
        repo.clear()
        assert len(repo) == 0
        assert len(repo.get_all_source_candidate_ids()) == 0
