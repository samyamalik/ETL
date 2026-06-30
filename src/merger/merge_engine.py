"""
Merge Engine — deterministically merges multiple SourceRecords into one CanonicalProfile.

Rules:
- Scalar fields: highest-priority non-null source wins
- List fields: union + deduplicate
- Experience/Education: union, dedup by composite key
- Links: merge dicts, highest-priority wins per key
"""

import os
import hashlib
import yaml
from src.schema.canonical import (
    CanonicalProfile, Email, Phone, Location, Skill,
    Experience, Education,
)
from src.normalizers.normalizers import (
    normalize_name, normalize_email_list, normalize_phone_list,
    normalize_location, normalize_skill_list, normalize_links,
    normalize_experience_list, normalize_education_list,
)
from src.logger import logger


def _load_priority():
    """Load source priority config."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "source_priority.yaml"
    )
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("priority", {})
    except Exception:
        # Default priority
        return {
            "ats_json": 1, "recruiter_csv": 2, "resume_pdf": 3,
            "resume_docx": 4, "github_profile": 5, "recruiter_notes": 6,
        }


def _get_priority(source_name, priority_map):
    """Get priority for a source (lower number = higher priority). Default = 99."""
    return priority_map.get(source_name, 99)


def _generate_candidate_id(emails, full_name):
    """
    Generate a deterministic candidate_id from emails and name.
    Same inputs always produce the same ID.
    """
    key_parts = sorted(emails) + [full_name.lower().strip() if full_name else ""]
    key_string = "|".join(key_parts)
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()[:16]


def merge_records(source_records):
    """
    Merge multiple SourceRecords into a single CanonicalProfile.

    Args:
        source_records: list of SourceRecord objects from different adapters.

    Returns:
        CanonicalProfile with merged, normalized data.
    """
    priority_map = _load_priority()
    profile = CanonicalProfile()

    if not source_records:
        logger.warning("merge", "", "No source records to merge")
        return profile

    # Sort records by priority (highest priority = lowest number = first)
    sorted_records = sorted(
        source_records,
        key=lambda r: _get_priority(r.source_name, priority_map)
    )

    logger.info("merge", "", f"Merging {len(sorted_records)} source records")

    # ── Scalar fields: highest-priority non-null wins ──

    # Full name
    name_candidates = []
    for record in sorted_records:
        if record.full_name:
            normalized = normalize_name(record.full_name)
            if normalized:
                name_candidates.append({
                    "value": normalized,
                    "source": record.source_name,
                    "priority": _get_priority(record.source_name, priority_map),
                })
    if name_candidates:
        profile.full_name = name_candidates[0]["value"]  # Already sorted by priority

    # Headline
    for record in sorted_records:
        if record.headline:
            profile.headline = record.headline.strip()
            break

    # Years experience
    for record in sorted_records:
        if record.years_experience is not None:
            profile.years_experience = record.years_experience
            break

    # Location
    for record in sorted_records:
        if record.location:
            loc_dict = normalize_location(record.location)
            if loc_dict:
                profile.location = Location(
                    city=loc_dict.get("city"),
                    state=loc_dict.get("state"),
                    country=loc_dict.get("country"),
                    raw=loc_dict.get("raw", ""),
                    source=record.source_name,
                )
                break

    # ── List fields: union + deduplicate ──

    # Emails
    all_emails = []
    for record in sorted_records:
        normalized_emails = normalize_email_list(record.emails)
        for email in normalized_emails:
            all_emails.append({"address": email, "source": record.source_name})

    seen_emails = set()
    for item in all_emails:
        if item["address"] not in seen_emails:
            seen_emails.add(item["address"])
            profile.emails.append(Email(
                address=item["address"],
                source=item["source"],
            ))

    # Phones
    all_phones = []
    for record in sorted_records:
        normalized_phones = normalize_phone_list(record.phones)
        for phone in normalized_phones:
            all_phones.append({"number": phone, "source": record.source_name})

    seen_phones = set()
    for item in all_phones:
        if item["number"] not in seen_phones:
            seen_phones.add(item["number"])
            profile.phones.append(Phone(
                number=item["number"],
                source=item["source"],
            ))

    # Skills
    all_skills = []
    for record in sorted_records:
        normalized_skills = normalize_skill_list(record.skills)
        for skill in normalized_skills:
            all_skills.append({"name": skill, "source": record.source_name})

    seen_skills = set()
    for item in all_skills:
        if item["name"] not in seen_skills:
            seen_skills.add(item["name"])
            profile.skills.append(Skill(
                name=item["name"],
                source=item["source"],
            ))

    # Links
    merged_links = {}
    # Process in reverse priority order so highest priority overwrites
    for record in reversed(sorted_records):
        normalized = normalize_links(record.links)
        merged_links.update(normalized)
    profile.links = merged_links

    # ── Experience: union, dedup by (company, title, start_date) ──
    all_experience = []
    for record in sorted_records:
        normalized_exps = normalize_experience_list(record.experience)
        for exp in normalized_exps:
            exp["source"] = record.source_name
            all_experience.append(exp)

    seen_exp_keys = set()
    for exp in all_experience:
        key = (
            exp.get("company", "").lower(),
            exp.get("title", "").lower(),
            exp.get("start_date", ""),
        )
        if key not in seen_exp_keys:
            seen_exp_keys.add(key)
            profile.experience.append(Experience(
                company=exp.get("company", ""),
                title=exp.get("title", ""),
                start_date=exp.get("start_date"),
                end_date=exp.get("end_date"),
                is_current=exp.get("is_current", False),
                description=exp.get("description", ""),
                source=exp.get("source", ""),
            ))

    # Sort experience by start_date descending
    profile.experience.sort(
        key=lambda x: x.start_date or "0000", reverse=True
    )

    # ── Education: union, dedup by (institution, degree) ──
    all_education = []
    for record in sorted_records:
        normalized_edus = normalize_education_list(record.education)
        for edu in normalized_edus:
            edu["source"] = record.source_name
            all_education.append(edu)

    seen_edu_keys = set()
    for edu in all_education:
        key = (
            edu.get("institution", "").lower(),
            edu.get("degree", "").lower(),
        )
        if key not in seen_edu_keys:
            seen_edu_keys.add(key)
            profile.education.append(Education(
                institution=edu.get("institution", ""),
                degree=edu.get("degree", ""),
                field_of_study=edu.get("field_of_study", ""),
                start_date=edu.get("start_date"),
                end_date=edu.get("end_date"),
                source=edu.get("source", ""),
            ))

    # ── Generate candidate ID ──
    email_addresses = [e.address for e in profile.emails]
    profile.candidate_id = _generate_candidate_id(email_addresses, profile.full_name)

    logger.info("merge", "", f"Merged profile: {profile.full_name} ({profile.candidate_id})")
    return profile
