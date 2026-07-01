"""GitHub Profile Extractor.

Supports extracting candidate profiles from:
- A cached JSON file (locally stored REST API responses).
- A live GitHub profile URL (using the REST API).
"""

import json
import logging
from pathlib import Path
import urllib.parse

import httpx

from candidate_transformer.domain.enums import ExtractionMethod, SourceType
from candidate_transformer.domain.exceptions import ExtractionError
from candidate_transformer.domain.interfaces.extractor import BaseExtractor
from candidate_transformer.domain.models.evidence import Evidence
from candidate_transformer.domain.models.input import SourceDescriptor
from candidate_transformer.pipeline.context import PipelineContext


class GitHubExtractor(BaseExtractor):
    """Concrete extractor for GitHub profiles."""

    @property
    def source_type(self) -> SourceType:
        return SourceType.GITHUB

    def extract(
        self,
        source: SourceDescriptor,
        ctx: PipelineContext,
    ) -> list[Evidence]:
        """Extract evidence from a cached GitHub JSON file or a live GitHub API URL."""
        # Check if the source path is a URL or a file path
        is_url = source.path.startswith("http://") or source.path.startswith("https://") or "github.com" in source.path

        if is_url:
            ctx.logger.info("Extracting from live GitHub URL: %s", source.path)
            raw_data = self._fetch_live_api(source.path, ctx)
        else:
            ctx.logger.info("Extracting from cached GitHub file: %s", source.path)
            raw_data = self._read_cached_file(source.path)

        if not raw_data:
            return []

        # The raw_data could be a direct GitHub User Profile API response,
        # or a custom combined structure containing {"profile": ..., "repos": ...} or similar.
        profile = raw_data.get("profile", raw_data) if isinstance(raw_data, dict) else {}
        repos = raw_data.get("repos", []) if isinstance(raw_data, dict) else []

        # Retrieve candidate login name
        login = profile.get("login")
        name_val = profile.get("name")
        email_val = profile.get("email")

        # Fallbacks for unique candidate ID
        if email_val and isinstance(email_val, str) and email_val.strip():
            source_candidate_id = f"github_cand_{email_val.strip().lower()}"
        elif login and isinstance(login, str) and login.strip():
            source_candidate_id = f"github_cand_{login.strip().lower()}"
        elif name_val and isinstance(name_val, str) and name_val.strip():
            source_candidate_id = f"github_cand_{name_val.strip().lower().replace(' ', '_')}"
        else:
            source_candidate_id = f"github_cand_unknown"

        evidences: list[Evidence] = []
        method = ExtractionMethod.API_FETCH if is_url else ExtractionMethod.JSON_PARSE

        # Extract name
        if name_val and isinstance(name_val, str) and name_val.strip():
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="full_name",
                    raw_value=name_val.strip(),
                    confidence=0.9,
                    extraction_method=method,
                )
            )

        # Extract emails
        if email_val and isinstance(email_val, str) and email_val.strip():
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="emails",
                    raw_value=[email_val.strip()],
                    confidence=0.95,
                    extraction_method=method,
                )
            )

        # Extract location
        loc_str = profile.get("location")
        if loc_str and isinstance(loc_str, str) and loc_str.strip():
            # A simple comma-split location parsing heuristic
            parts = [p.strip() for p in loc_str.split(",") if p.strip()]
            city = parts[0] if len(parts) > 0 else None
            region = parts[1] if len(parts) > 1 else None
            country = parts[-1] if len(parts) > 0 else None
            location_dict = {
                "city": city,
                "region": region,
                "country": country,
            }
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="location",
                    raw_value=location_dict,
                    confidence=0.8,
                    extraction_method=method,
                )
            )

        # Extract headline (bio)
        bio = profile.get("bio")
        if bio and isinstance(bio, str) and bio.strip():
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="headline",
                    raw_value=bio.strip(),
                    confidence=0.85,
                    extraction_method=method,
                )
            )

        # Extract links (github and portfolio from blog)
        links_dict = {
            "github": profile.get("html_url"),
            "portfolio": profile.get("blog") if profile.get("blog") else None,
            "linkedin": None,
            "other": [],
        }
        if links_dict["github"] or links_dict["portfolio"]:
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="links",
                    raw_value=links_dict,
                    confidence=0.9,
                    extraction_method=method,
                )
            )

        # Extract skills (from repository languages or "languages" keys)
        # We can look in raw_data["languages"] if it exists, or compute it from repos
        languages = set()
        if repos and isinstance(repos, list):
            for repo in repos:
                if isinstance(repo, dict) and repo.get("language"):
                    languages.add(repo["language"])
        elif isinstance(raw_data, dict) and "languages" in raw_data:
            if isinstance(raw_data["languages"], list):
                languages.update(raw_data["languages"])

        if languages:
            skills_list = [
                {
                    "name": lang.strip(),
                    "confidence": 0.8,
                    "sources": ["github"],
                }
                for lang in languages
                if lang
            ]
            evidences.append(
                Evidence.create(
                    source_type=self.source_type,
                    source_ref=source.path,
                    source_candidate_id=source_candidate_id,
                    field_name="skills",
                    raw_value=skills_list,
                    confidence=0.85,
                    extraction_method=method,
                )
            )

        return evidences

    def _read_cached_file(self, file_path_str: str) -> dict:
        """Read cached GitHub JSON file from disk."""
        path = Path(file_path_str)
        if not path.exists():
            raise ExtractionError(
                f"GitHub cached JSON file not found: {file_path_str}",
                context={"path": file_path_str},
            )
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            raise ExtractionError(
                f"Failed to read/parse cached GitHub JSON file {file_path_str}: {str(e)}",
                context={"path": file_path_str, "error": str(e)},
            ) from e

    def _fetch_live_api(self, url: str, ctx: PipelineContext) -> dict:
        """Fetch live GitHub profile from public REST API."""
        # Parse username from URL: e.g. https://github.com/octocat or github.com/octocat
        username = self._parse_username(url)
        if not username:
            ctx.add_warning(f"Could not parse GitHub username from URL '{url}'. Skipping live fetch.")
            return {}

        api_url = f"https://api.github.com/users/{username}"
        repos_url = f"https://api.github.com/users/{username}/repos"

        try:
            headers = {"User-Agent": "Candidate-Transformer-Pipeline"}
            # Use synchronous HTTPX client
            with httpx.Client(timeout=10.0) as client:
                # Fetch user profile
                profile_res = client.get(api_url, headers=headers)
                if profile_res.status_code == 404:
                    ctx.add_warning(f"GitHub user '{username}' not found (HTTP 404).")
                    return {}
                elif profile_res.status_code in (403, 429):
                    ctx.add_warning(f"GitHub API rate limited or forbidden (HTTP {profile_res.status_code}).")
                    return {}
                profile_res.raise_for_status()
                profile_data = profile_res.json()

                # Fetch repositories to get languages
                repos_data = []
                repos_res = client.get(repos_url, headers=headers)
                if repos_res.status_code == 200:
                    repos_data = repos_res.json()
                else:
                    ctx.add_warning(f"Failed to fetch repos for GitHub user '{username}' (HTTP {repos_res.status_code}).")

                return {
                    "profile": profile_data,
                    "repos": repos_data,
                }
        except Exception as e:
            ctx.add_warning(f"Failed to fetch live GitHub API for user '{username}': {str(e)}")
            return {}

    def _parse_username(self, url: str) -> str | None:
        """Parse github username from a GitHub URL."""
        # Strip protocols
        url_clean = url.replace("http://", "").replace("https://", "")
        # Handle trailing slash
        url_clean = url_clean.rstrip("/")
        # Path split
        parts = url_clean.split("/")
        # Expected: ['github.com', 'username'] or similar
        for idx, part in enumerate(parts):
            if "github.com" in part and idx + 1 < len(parts):
                return parts[idx + 1]
        # Fallback if it's just the username or just github.com/username
        if len(parts) == 1 and parts[0] != "github.com":
            return parts[0]
        return None
