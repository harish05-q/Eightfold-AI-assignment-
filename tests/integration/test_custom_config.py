"""Integration test for custom configuration runs."""

from pathlib import Path
from candidate_transformer.config.models import OutputConfig
from candidate_transformer.domain.models.input import InputManifest
from candidate_transformer.factory import create_standard_orchestrator

def test_custom_config_run() -> None:
    manifest_path = Path("sample_inputs/manifest.json")
    manifest = InputManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    
    config_path = Path("sample_inputs/custom_config.json")
    config = OutputConfig.model_validate_json(config_path.read_text(encoding="utf-8"))
    
    orchestrator = create_standard_orchestrator()
    result = orchestrator.run(manifest, config)
    
    assert len(result.errors) == 0
    assert len(result.candidates) == 1
    c = result.candidates[0]
    
    # Custom config only asked for candidate_id, full_name, emails, skills
    assert "candidate_id" in c
    assert "full_name" in c
    assert "emails" in c
    assert "skills" in c
    assert "phones" not in c
    assert "location" not in c
    assert "experience" not in c
