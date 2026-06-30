"""
Confidence Scorer — assigns per-field and overall confidence scores.

Formula: confidence = source_trust × extraction_quality × agreement_bonus
"""

import os
import yaml
from src.logger import logger


def _load_trust_weights():
    """Load source trust weights from config."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "source_priority.yaml"
    )
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("trust_weights", {})
    except Exception:
        return {
            "ats_json": 0.95, "recruiter_csv": 0.85, "resume_pdf": 0.75,
            "resume_docx": 0.75, "github_profile": 0.70, "recruiter_notes": 0.50,
        }


# Extraction method quality multipliers
EXTRACTION_QUALITY = {
    "structured": 1.0,
    "regex": 0.7,
    "heuristic": 0.6,
    "unknown": 0.5,
}

# Field importance weights for overall confidence
FIELD_WEIGHTS = {
    "full_name": 1.0,
    "emails": 0.9,
    "phones": 0.7,
    "location": 0.6,
    "headline": 0.5,
    "years_experience": 0.6,
    "skills": 0.7,
    "experience": 0.8,
    "education": 0.7,
    "links": 0.3,
}

AGREEMENT_BONUS = 0.1


def _get_source_trust(source_name, trust_weights):
    """Get trust weight for a source. Default 0.5."""
    return trust_weights.get(source_name, 0.5)


def _get_extraction_quality(extraction_method):
    """Get quality multiplier for an extraction method."""
    return EXTRACTION_QUALITY.get(extraction_method, 0.5)


def _count_source_agreements(field_name, source_records, profile):
    """Count how many sources agree on a field value."""
    if field_name == "full_name":
        values = [r.full_name for r in source_records if r.full_name]
        # Normalize for comparison
        normalized = [v.strip().lower() for v in values]
        if normalized:
            most_common = max(set(normalized), key=normalized.count)
            return normalized.count(most_common)
    elif field_name == "emails":
        all_emails = set()
        for r in source_records:
            for e in r.emails:
                all_emails.add(e.lower().strip())
        return len([r for r in source_records if any(e.lower().strip() in all_emails for e in r.emails)])
    elif field_name == "skills":
        return len([r for r in source_records if r.skills])
    return 1


def score_profile(profile, source_records):
    """
    Assign confidence scores to every field in the profile.

    Args:
        profile: CanonicalProfile to score (modified in place)
        source_records: list of SourceRecord used to build the profile

    Returns:
        The same profile with confidence scores populated.
    """
    trust_weights = _load_trust_weights()
    field_confidences = {}

    # Build a map of source_name -> extraction_method
    source_methods = {}
    for record in source_records:
        source_methods[record.source_name] = record.extraction_method

    # ── Score scalar fields ──

    # Full name
    if profile.full_name:
        source = _find_source_for_scalar(source_records, "full_name", profile.full_name)
        trust = _get_source_trust(source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(source, "unknown"))
        agreement = _count_source_agreements("full_name", source_records, profile)
        bonus = AGREEMENT_BONUS if agreement >= 2 else 0.0
        field_confidences["full_name"] = min(trust * quality + bonus, 1.0)
    else:
        field_confidences["full_name"] = 0.0

    # Headline
    if profile.headline:
        source = _find_source_for_scalar(source_records, "headline", profile.headline)
        trust = _get_source_trust(source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(source, "unknown"))
        field_confidences["headline"] = min(trust * quality, 1.0)
    else:
        field_confidences["headline"] = 0.0

    # Years experience
    if profile.years_experience is not None:
        source = _find_source_for_yoe(source_records, profile.years_experience)
        trust = _get_source_trust(source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(source, "unknown"))
        field_confidences["years_experience"] = min(trust * quality, 1.0)
    else:
        field_confidences["years_experience"] = 0.0

    # Location
    if profile.location:
        trust = _get_source_trust(profile.location.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(profile.location.source, "unknown"))
        conf = min(trust * quality, 1.0)
        profile.location.confidence = conf
        field_confidences["location"] = conf
    else:
        field_confidences["location"] = 0.0

    # ── Score list fields ──

    # Emails
    for email in profile.emails:
        trust = _get_source_trust(email.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(email.source, "unknown"))
        email.confidence = min(trust * quality, 1.0)
    field_confidences["emails"] = (
        max(e.confidence for e in profile.emails) if profile.emails else 0.0
    )

    # Phones
    for phone in profile.phones:
        trust = _get_source_trust(phone.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(phone.source, "unknown"))
        phone.confidence = min(trust * quality, 1.0)
    field_confidences["phones"] = (
        max(p.confidence for p in profile.phones) if profile.phones else 0.0
    )

    # Skills
    for skill in profile.skills:
        trust = _get_source_trust(skill.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(skill.source, "unknown"))
        agreement_count = sum(
            1 for r in source_records
            if skill.name.lower() in [s.lower() for s in r.skills]
        )
        bonus = AGREEMENT_BONUS if agreement_count >= 2 else 0.0
        skill.confidence = min(trust * quality + bonus, 1.0)
    field_confidences["skills"] = (
        sum(s.confidence for s in profile.skills) / len(profile.skills)
        if profile.skills else 0.0
    )

    # Experience
    for exp in profile.experience:
        trust = _get_source_trust(exp.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(exp.source, "unknown"))
        exp.confidence = min(trust * quality, 1.0)
    field_confidences["experience"] = (
        sum(e.confidence for e in profile.experience) / len(profile.experience)
        if profile.experience else 0.0
    )

    # Education
    for edu in profile.education:
        trust = _get_source_trust(edu.source, trust_weights)
        quality = _get_extraction_quality(source_methods.get(edu.source, "unknown"))
        edu.confidence = min(trust * quality, 1.0)
    field_confidences["education"] = (
        sum(e.confidence for e in profile.education) / len(profile.education)
        if profile.education else 0.0
    )

    # Links
    field_confidences["links"] = 0.7 if profile.links else 0.0

    # ── Overall confidence: weighted mean ──
    total_weight = 0.0
    weighted_sum = 0.0
    for field_name, conf in field_confidences.items():
        weight = FIELD_WEIGHTS.get(field_name, 0.5)
        weighted_sum += conf * weight
        total_weight += weight

    profile.overall_confidence = round(weighted_sum / total_weight, 4) if total_weight > 0 else 0.0

    logger.info("scoring", "", f"Overall confidence: {profile.overall_confidence}")
    return profile


def _find_source_for_scalar(source_records, field_name, value):
    """Find which source provided a scalar field value."""
    for record in source_records:
        record_value = getattr(record, field_name, None)
        if record_value and record_value.strip().lower() == value.strip().lower():
            return record.source_name
    # Fallback: return first source that has the field
    for record in source_records:
        if getattr(record, field_name, None):
            return record.source_name
    return ""


def _find_source_for_yoe(source_records, value):
    """Find which source provided years_experience."""
    for record in source_records:
        if record.years_experience == value:
            return record.source_name
    return ""
