"""Basic integration tests for the FastAPI endpoint."""

from fastapi.testclient import TestClient

from candidate_transformer.api import app

client = TestClient(app)

def test_transform_empty_manifest() -> None:
    """Test the /transform endpoint with an empty manifest."""
    response = client.post(
        "/transform",
        json={"manifest": {"sources": []}}
    )
    assert response.status_code == 200
    data = response.json()
    assert "run_id" in data
    assert "candidates" in data
    assert len(data["candidates"]) == 0
    assert "timing" in data
    assert "total" in data["timing"]
