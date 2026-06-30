"""
Source record — the intermediate representation that every adapter produces.

Each adapter extracts raw data into this flat structure. The normalizer
then converts these into canonical types before merging.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SourceRecord:
    """
    Flat intermediate representation from a single source.

    Every field is Optional because any source may have partial data.
    The 'source_name' field tags where this data came from.
    """
    source_name: str = ""               # e.g. "ats_json", "resume_pdf"
    extraction_method: str = "unknown"  # "structured", "regex", "heuristic"

    # Identity
    full_name: Optional[str] = None
    emails: list = field(default_factory=list)       # list of raw email strings
    phones: list = field(default_factory=list)       # list of raw phone strings
    location: Optional[str] = None                   # raw location string

    # Professional
    headline: Optional[str] = None
    years_experience: Optional[float] = None
    skills: list = field(default_factory=list)       # list of raw skill strings
    links: dict = field(default_factory=dict)        # {"github": "...", ...}

    # Experience
    experience: list = field(default_factory=list)   # list of dicts

    # Education
    education: list = field(default_factory=list)    # list of dicts

    # Metadata
    errors: list = field(default_factory=list)       # Errors encountered during extraction
    raw_text: str = ""                               # Original text for unstructured sources
