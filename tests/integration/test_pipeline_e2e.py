"""Integration tests for the end-to-end pipeline execution."""

from pathlib import Path

from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.input import InputManifest
from candidate_transformer.factory import create_standard_orchestrator


def test_pipeline_e2e_with_sample_data() -> None:
    """Verify that the 4 sample files merge into exactly 1 candidate and validate."""
    manifest_path = Path("sample_inputs/manifest.json")
    manifest = InputManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    
    config = OutputConfig()
    
    orchestrator = create_standard_orchestrator()
    result = orchestrator.run(manifest, config)
    
    # Assert no pipeline crashes
    assert len(result.errors) == 0, f"Pipeline had errors: {result.errors}"
    
    # Assert all 4 sources resolved to a single candidate
    assert len(result.candidates) == 1
    
    candidate = result.candidates[0]
    assert candidate["full_name"] == "Alice B. Engineer"
    
    # Both emails should be captured
    assert "alice.eng@email.com" in candidate["emails"]
    assert "alice@example.com" in candidate["emails"]
    
    # Both phones should be captured (normalized)
    assert "+15551234567" in candidate["phones"]
    assert "5551234567" in candidate["phones"]
    
    # Skills from ATS and Resume should be merged
    skill_names = [s["name"] for s in candidate["skills"]]
    assert "Go" in skill_names
    assert "System Design" in skill_names
    assert "Python" in skill_names
    assert "SQL" in skill_names
    assert "FastAPI" in skill_names
    
    # Experience from ATS and CSV
    assert len(candidate["experience"]) == 2
