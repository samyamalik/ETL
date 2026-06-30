"""
Provenance Tracker — records the origin and method for every value in the profile.

Every non-null field gets a ProvenanceEntry recording:
- What source provided it
- How it was extracted
- What confidence it has
- What alternatives were available from other sources
"""

from datetime import datetime, timezone
from src.schema.canonical import ProvenanceEntry
from src.logger import logger


def track_provenance(profile, source_records):
    """
    Build provenance entries for every field in the canonical profile.

    Args:
        profile: CanonicalProfile (modified in place to add provenance[])
        source_records: list of SourceRecord used to build this profile

    Returns:
        The same profile with provenance[] populated.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    provenance = []

    # Build source method map
    source_methods = {r.source_name: r.extraction_method for r in source_records}

    # ── Full name ──
    if profile.full_name:
        alternatives = []
        winner_source = ""
        for record in source_records:
            if record.full_name:
                if not winner_source:
                    winner_source = record.source_name
                else:
                    alternatives.append({
                        "value": record.full_name,
                        "source": record.source_name,
                    })
        provenance.append(ProvenanceEntry(
            field_path="full_name",
            value=profile.full_name,
            source=winner_source,
            method=source_methods.get(winner_source, "unknown"),
            confidence=0.0,  # Will be set from scoring
            timestamp=timestamp,
            alternatives=alternatives,
        ))

    # ── Emails ──
    for i, email in enumerate(profile.emails):
        provenance.append(ProvenanceEntry(
            field_path=f"emails[{i}]",
            value=email.address,
            source=email.source,
            method=source_methods.get(email.source, "unknown"),
            confidence=email.confidence,
            timestamp=timestamp,
        ))

    # ── Phones ──
    for i, phone in enumerate(profile.phones):
        provenance.append(ProvenanceEntry(
            field_path=f"phones[{i}]",
            value=phone.number,
            source=phone.source,
            method=source_methods.get(phone.source, "unknown"),
            confidence=phone.confidence,
            timestamp=timestamp,
        ))

    # ── Location ──
    if profile.location:
        provenance.append(ProvenanceEntry(
            field_path="location",
            value=profile.location.raw or f"{profile.location.city}, {profile.location.state}",
            source=profile.location.source,
            method=source_methods.get(profile.location.source, "unknown"),
            confidence=profile.location.confidence,
            timestamp=timestamp,
            alternatives=_collect_location_alternatives(source_records, profile.location.source),
        ))

    # ── Headline ──
    if profile.headline:
        alternatives = []
        winner_source = ""
        for record in source_records:
            if record.headline:
                if not winner_source:
                    winner_source = record.source_name
                else:
                    alternatives.append({
                        "value": record.headline,
                        "source": record.source_name,
                    })
        provenance.append(ProvenanceEntry(
            field_path="headline",
            value=profile.headline,
            source=winner_source,
            method=source_methods.get(winner_source, "unknown"),
            timestamp=timestamp,
            alternatives=alternatives,
        ))

    # ── Years experience ──
    if profile.years_experience is not None:
        winner_source = ""
        alternatives = []
        for record in source_records:
            if record.years_experience is not None:
                if not winner_source:
                    winner_source = record.source_name
                else:
                    alternatives.append({
                        "value": str(record.years_experience),
                        "source": record.source_name,
                    })
        provenance.append(ProvenanceEntry(
            field_path="years_experience",
            value=str(profile.years_experience),
            source=winner_source,
            method=source_methods.get(winner_source, "unknown"),
            timestamp=timestamp,
            alternatives=alternatives,
        ))

    # ── Skills ──
    for i, skill in enumerate(profile.skills):
        provenance.append(ProvenanceEntry(
            field_path=f"skills[{i}]",
            value=skill.name,
            source=skill.source,
            method=source_methods.get(skill.source, "unknown"),
            confidence=skill.confidence,
            timestamp=timestamp,
        ))

    # ── Experience ──
    for i, exp in enumerate(profile.experience):
        provenance.append(ProvenanceEntry(
            field_path=f"experience[{i}]",
            value=f"{exp.title} at {exp.company}",
            source=exp.source,
            method=source_methods.get(exp.source, "unknown"),
            confidence=exp.confidence,
            timestamp=timestamp,
        ))

    # ── Education ──
    for i, edu in enumerate(profile.education):
        provenance.append(ProvenanceEntry(
            field_path=f"education[{i}]",
            value=f"{edu.degree} at {edu.institution}",
            source=edu.source,
            method=source_methods.get(edu.source, "unknown"),
            confidence=edu.confidence,
            timestamp=timestamp,
        ))

    profile.provenance = provenance
    logger.info("provenance", "", f"Tracked {len(provenance)} provenance entries")
    return profile


def _collect_location_alternatives(source_records, winner_source):
    """Collect location values from non-winning sources."""
    alternatives = []
    for record in source_records:
        if record.location and record.source_name != winner_source:
            alternatives.append({
                "value": record.location,
                "source": record.source_name,
            })
    return alternatives
