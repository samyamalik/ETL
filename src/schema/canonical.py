"""
Canonical schema — the single source of truth for candidate profiles.

This schema is IMMUTABLE. No pipeline stage may add, remove, or rename fields.
All sub-models use simple dataclasses for clarity.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Email:
    """A normalized email address with provenance."""
    address: str
    source: str = ""
    confidence: float = 0.0


@dataclass
class Phone:
    """A normalized phone number (E.164 format) with provenance."""
    number: str
    phone_type: str = "unknown"  # mobile, work, home, unknown
    source: str = ""
    confidence: float = 0.0


@dataclass
class Location:
    """A normalized location."""
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    raw: str = ""
    source: str = ""
    confidence: float = 0.0


@dataclass
class Skill:
    """A canonical skill name with provenance."""
    name: str
    source: str = ""
    confidence: float = 0.0


@dataclass
class Experience:
    """A single work experience entry."""
    company: str = ""
    title: str = ""
    start_date: Optional[str] = None   # ISO 8601 or None
    end_date: Optional[str] = None     # ISO 8601 or None
    is_current: bool = False
    description: str = ""
    source: str = ""
    confidence: float = 0.0


@dataclass
class Education:
    """A single education entry."""
    institution: str = ""
    degree: str = ""
    field_of_study: str = ""
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    source: str = ""
    confidence: float = 0.0


@dataclass
class ProvenanceEntry:
    """Tracks the origin and method for every value in the profile."""
    field_path: str = ""        # e.g. "full_name", "skills[2]"
    value: str = ""             # String representation of the value
    source: str = ""            # e.g. "ats_json", "resume_pdf"
    method: str = ""            # e.g. "direct_extraction", "regex", "merge_priority"
    confidence: float = 0.0
    timestamp: str = ""         # ISO 8601
    alternatives: list = field(default_factory=list)  # Other values that lost


@dataclass
class CanonicalProfile:
    """
    The ONE canonical profile produced by the pipeline.

    This dataclass is the single source of truth. It is NEVER modified
    by the projection engine or runtime config.
    """
    candidate_id: str = ""
    full_name: str = ""
    emails: list = field(default_factory=list)         # list[Email]
    phones: list = field(default_factory=list)         # list[Phone]
    location: Optional[Location] = None
    links: dict = field(default_factory=dict)          # {"github": "...", "linkedin": "..."}
    headline: str = ""
    years_experience: Optional[float] = None
    skills: list = field(default_factory=list)         # list[Skill]
    experience: list = field(default_factory=list)     # list[Experience]
    education: list = field(default_factory=list)      # list[Education]
    provenance: list = field(default_factory=list)     # list[ProvenanceEntry]
    overall_confidence: float = 0.0
