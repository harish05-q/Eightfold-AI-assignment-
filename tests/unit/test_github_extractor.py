"""Unit tests for GitHubExtractor."""

import json
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from candidate_transformer.domain.enums import SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.extractors.github_extractor import GitHubExtractor
from candidate_transformer.pipeline.context import PipelineContext


class TestGitHubExtractor:
    """Tests for GitHubExtractor."""

    def test_source_type(self) -> None:
        """Extractor reports correct source type."""
        extractor = GitHubExtractor()
        assert extractor.source_type == SourceType.GITHUB

    def test_extract_cached_json(self, tmp_path: Path, pipeline_context: PipelineContext) -> None:
        """Valid cached GitHub profile JSON extracts all expected fields."""
        github_data = {
            "profile": {
                "login": "octocat",
                "name": "The Octocat",
                "email": "octocat@github.com",
                "location": "San Francisco, CA",
                "bio": "Testing GitHub bio",
                "blog": "https://github.blog",
                "html_url": "https://github.com/octocat"
            },
            "repos": [
                {"name": "hello-world", "language": "Python"},
                {"name": "spoon-knife", "language": "JavaScript"}
            ]
        }
        json_file = tmp_path / "github_cache.json"
        json_file.write_text(json.dumps(github_data), encoding="utf-8")

        extractor = GitHubExtractor()
        source = SourceDescriptor(source_type=SourceType.GITHUB, path=str(json_file))
        evidences = extractor.extract(source, pipeline_context)

        fields = {e.field_name: e for e in evidences}
        assert "full_name" in fields
        assert "emails" in fields
        assert "location" in fields
        assert "headline" in fields
        assert "links" in fields
        assert "skills" in fields

        assert fields["full_name"].raw_value == "The Octocat"
        assert fields["emails"].raw_value == ["octocat@github.com"]
        assert fields["location"].raw_value == {"city": "San Francisco", "region": "CA", "country": "CA"} # Simple heuristic split
        assert fields["headline"].raw_value == "Testing GitHub bio"
        assert fields["links"].raw_value["github"] == "https://github.com/octocat"
        assert fields["links"].raw_value["portfolio"] == "https://github.blog"

        # Check languages extracted as skills
        skills = fields["skills"].raw_value
        assert len(skills) == 2
        skill_names = [s["name"] for s in skills]
        assert "Python" in skill_names
        assert "JavaScript" in skill_names

    def test_extract_missing_cached_file_raises(self, pipeline_context: PipelineContext) -> None:
        """Missing cached file raises ExtractionError."""
        extractor = GitHubExtractor()
        source = SourceDescriptor(source_type=SourceType.GITHUB, path="nonexistent_github.json")
        with pytest.raises(ExtractionError, match="GitHub cached JSON file not found"):
            extractor.extract(source, pipeline_context)

    @patch("httpx.Client")
    def test_extract_live_api_success(self, mock_client_class: MagicMock, pipeline_context: PipelineContext) -> None:
        """Fetching from live GitHub URL performs HTTP queries and parses payload."""
        # Setup mock HTTP responses
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        # Mock profile response
        profile_response = MagicMock()
        profile_response.status_code = 200
        profile_response.json.return_value = {
            "login": "octocat",
            "name": "The Octocat",
            "email": "octocat@github.com",
            "location": "San Francisco",
            "bio": "Live Bio",
            "blog": "https://github.blog",
            "html_url": "https://github.com/octocat"
        }

        # Mock repos response
        repos_response = MagicMock()
        repos_res_data = [
            {"language": "Python"},
            {"language": "TypeScript"}
        ]
        repos_response.status_code = 200
        repos_response.json.return_value = repos_res_data

        # Configure get behavior
        mock_client.get.side_effect = [profile_response, repos_response]

        extractor = GitHubExtractor()
        source = SourceDescriptor(source_type=SourceType.GITHUB, path="https://github.com/octocat")
        evidences = extractor.extract(source, pipeline_context)

        fields = {e.field_name: e for e in evidences}
        assert "full_name" in fields
        assert "emails" in fields
        assert "skills" in fields
        assert fields["headline"].raw_value == "Live Bio"

        skills = fields["skills"].raw_value
        assert len(skills) == 2
        skill_names = [s["name"] for s in skills]
        assert "Python" in skill_names
        assert "TypeScript" in skill_names

    @patch("httpx.Client")
    def test_extract_live_api_404_graceful(self, mock_client_class: MagicMock, pipeline_context: PipelineContext) -> None:
        """404 response on live fetch adds warning and returns empty evidence list."""
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client

        profile_response = MagicMock()
        profile_response.status_code = 404
        mock_client.get.return_value = profile_response

        extractor = GitHubExtractor()
        source = SourceDescriptor(source_type=SourceType.GITHUB, path="https://github.com/nonexistentuser")
        evidences = extractor.extract(source, pipeline_context)

        assert evidences == []
        assert len(pipeline_context.warnings) > 0
        assert "not found" in pipeline_context.warnings[0]
