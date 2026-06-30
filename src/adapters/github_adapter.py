"""
GitHub Adapter — extracts candidate data from GitHub profiles via the REST API.

Handles: missing profile, rate limiting, API errors, private profiles.
"""

import re
from src.adapters.base_adapter import BaseAdapter
from src.schema.source_record import SourceRecord
from src.logger import logger


class GithubAdapter(BaseAdapter):
    """Adapter for GitHub profile data via REST API."""

    def __init__(self, api_token=None):
        super().__init__()
        self.source_name = "github_profile"
        self.supported_extensions = []  # Not file-based
        self.api_token = api_token
        self.base_url = "https://api.github.com"

    def can_handle(self, input_data):
        """Check if the input looks like a GitHub username or URL."""
        if not input_data or not isinstance(input_data, str):
            return False
        return ("github.com" in input_data.lower() or
                re.match(r'^[a-zA-Z0-9\-]+$', input_data))

    def extract(self, input_data):
        """
        Extract candidate data from a GitHub profile.

        Args:
            input_data: GitHub username or profile URL.
        """
        username = self._extract_username(input_data)
        if not username:
            logger.warning("ingest", self.source_name, f"Invalid GitHub input: {input_data}")
            return [self._empty_record_with_error(f"Invalid GitHub input: {input_data}")]

        # Try to fetch from GitHub API
        try:
            import requests
            headers = {"Accept": "application/vnd.github.v3+json"}
            if self.api_token:
                headers["Authorization"] = f"token {self.api_token}"

            url = f"{self.base_url}/users/{username}"
            response = requests.get(url, headers=headers, timeout=10)

            if response.status_code == 404:
                logger.warning("ingest", self.source_name, f"GitHub user not found: {username}")
                return [self._empty_record_with_error(f"GitHub user not found: {username}")]

            if response.status_code == 403:
                logger.warning("ingest", self.source_name, "GitHub API rate limit exceeded")
                return [self._empty_record_with_error("GitHub API rate limit exceeded")]

            if response.status_code != 200:
                logger.warning("ingest", self.source_name, f"GitHub API returned {response.status_code}")
                return [self._empty_record_with_error(f"GitHub API error: {response.status_code}")]

            data = response.json()
            if not isinstance(data, dict):
                return [self._empty_record_with_error("Invalid GitHub API response")]

            # Also fetch repos for language/skill data
            repos_url = f"{self.base_url}/users/{username}/repos?per_page=100&sort=updated"
            repos_response = requests.get(repos_url, headers=headers, timeout=10)
            repos = repos_response.json() if repos_response.status_code == 200 else []

            return [self._parse_profile(data, repos, username)]

        except ImportError:
            logger.error("ingest", self.source_name, "requests library not installed")
            return [self._empty_record_with_error("requests library not installed")]
        except Exception as e:
            logger.error("ingest", self.source_name, f"GitHub API error: {str(e)}")
            return [self._empty_record_with_error(f"GitHub API error: {str(e)}")]

    def _extract_username(self, input_data):
        """Extract GitHub username from URL or raw string."""
        if not input_data:
            return None
        input_data = input_data.strip().rstrip("/")

        # If it's a URL, extract the username part
        match = re.search(r'github\.com/([a-zA-Z0-9\-]+)', input_data)
        if match:
            return match.group(1)

        # If it looks like a plain username
        if re.match(r'^[a-zA-Z0-9\-]+$', input_data):
            return input_data

        return None

    def _parse_profile(self, data, repos, username):
        """Parse GitHub API response into a SourceRecord."""
        record = SourceRecord(
            source_name=self.source_name,
            extraction_method="structured",
        )

        record.full_name = data.get("name") or None
        record.headline = data.get("bio") or None
        record.location = data.get("location") or None

        # Email (if public)
        email = data.get("email")
        if email:
            record.emails = [email]

        # Links
        record.links["github"] = f"https://github.com/{username}"
        blog = data.get("blog")
        if blog:
            if not blog.startswith("http"):
                blog = "https://" + blog
            record.links["portfolio"] = blog

        twitter = data.get("twitter_username")
        if twitter:
            record.links["twitter"] = f"https://twitter.com/{twitter}"

        # Extract languages/skills from repos
        if isinstance(repos, list):
            languages = set()
            for repo in repos:
                if isinstance(repo, dict) and not repo.get("fork", False):
                    lang = repo.get("language")
                    if lang:
                        languages.add(lang)
                    # Also check topics
                    topics = repo.get("topics") or []
                    for topic in topics:
                        if topic:
                            languages.add(topic)
            record.skills = sorted(languages)

        logger.debug("ingest", self.source_name, f"Parsed GitHub profile: {username}")
        return record
