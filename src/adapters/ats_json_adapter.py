"""
ATS JSON Adapter — extracts candidate data from ATS (Applicant Tracking System) JSON files.

Handles: valid JSON, invalid JSON, missing keys, nested nulls.
"""

import json
import os
from src.adapters.base_adapter import BaseAdapter
from src.schema.source_record import SourceRecord
from src.logger import logger


class AtsJsonAdapter(BaseAdapter):
    """Adapter for ATS JSON files."""

    def __init__(self):
        super().__init__()
        self.source_name = "ats_json"
        self.supported_extensions = [".json"]

    def extract(self, input_data):
        """
        Extract candidate data from an ATS JSON file.

        Args:
            input_data: Path to the JSON file.

        Returns:
            list[SourceRecord]
        """
        if not input_data or not os.path.exists(input_data):
            logger.warning("ingest", self.source_name, f"File not found: {input_data}")
            return [self._empty_record_with_error(f"File not found: {input_data}")]

        if os.path.getsize(input_data) == 0:
            logger.warning("ingest", self.source_name, "JSON file is empty")
            return [self._empty_record_with_error("JSON file is empty")]

        try:
            with open(input_data, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            logger.error("ingest", self.source_name, f"Invalid JSON: {str(e)}")
            return [self._empty_record_with_error(f"Invalid JSON: {str(e)}")]
        except Exception as e:
            logger.error("ingest", self.source_name, f"Failed to read file: {str(e)}")
            return [self._empty_record_with_error(f"Failed to read file: {str(e)}")]

        # Handle both single object and list of candidates
        if isinstance(data, list):
            records = []
            for i, item in enumerate(data):
                if isinstance(item, dict):
                    records.append(self._parse_candidate(item))
                else:
                    logger.warning("ingest", self.source_name, f"Skipping non-dict item at index {i}")
            return records if records else [self._empty_record_with_error("No valid candidates in JSON array")]
        elif isinstance(data, dict):
            # Unwrap a top-level 'candidate' or 'candidates' wrapper if present
            if "candidates" in data and isinstance(data["candidates"], list):
                records = [self._parse_candidate(c) for c in data["candidates"] if isinstance(c, dict)]
                return records if records else [self._empty_record_with_error("No valid candidates")]
            elif "candidate" in data and isinstance(data["candidate"], dict):
                return [self._parse_candidate(data["candidate"])]
            else:
                return [self._parse_candidate(data)]
        else:
            return [self._empty_record_with_error("JSON root is not an object or array")]

    def _parse_candidate(self, data):
        """Parse a single candidate dict into a SourceRecord."""
        record = SourceRecord(
            source_name=self.source_name,
            extraction_method="structured",
        )

        # Name — try multiple common ATS key names
        record.full_name = (
            self._safe_str(data, "full_name")
            or self._safe_str(data, "name")
            or self._safe_str(data, "candidateName")
            or self._safe_str(data, "candidate_name")
        )

        # Contact block — many ATS systems nest email/phone under a 'contact' key
        contact = data.get("contact") or {}

        # Emails — could be string or list, top-level or inside 'contact'
        emails_raw = data.get("emails") or data.get("email") or contact.get("emails") or contact.get("email")
        if isinstance(emails_raw, str):
            record.emails = [emails_raw.strip()] if emails_raw.strip() else []
        elif isinstance(emails_raw, list):
            record.emails = [str(e).strip() for e in emails_raw if e]

        # Phones — top-level or inside 'contact'
        phones_raw = data.get("phones") or data.get("phone") or contact.get("phones") or contact.get("phone")
        if isinstance(phones_raw, str):
            record.phones = [phones_raw.strip()] if phones_raw.strip() else []
        elif isinstance(phones_raw, list):
            record.phones = [str(p).strip() for p in phones_raw if p]

        # Location
        loc = data.get("location")
        if isinstance(loc, str):
            record.location = loc
        elif isinstance(loc, dict):
            parts = [loc.get("city", ""), loc.get("state", ""), loc.get("country", "")]
            record.location = ", ".join(p for p in parts if p)

        # Headline — try currentRole, current_role, title, headline
        record.headline = (
            self._safe_str(data, "headline")
            or self._safe_str(data, "title")
            or self._safe_str(data, "currentRole")
            or self._safe_str(data, "current_role")
        )

        # Years experience — try multiple keys
        yoe = (
            data.get("years_experience")
            or data.get("experience_years")
            or data.get("yearsExperience")
            or data.get("total_experience")
        )
        if yoe is not None:
            try:
                record.years_experience = float(yoe)
            except (ValueError, TypeError):
                record.errors.append(f"Invalid years_experience: {yoe}")

        # Skills — handle both a flat list and a nested dict of categories
        # e.g. {"languages": [...], "core": [...], "tools": [...]}
        skills_raw = data.get("skills") or data.get("skill_list") or []
        all_skills = []
        if isinstance(skills_raw, list):
            all_skills = [str(s).strip() for s in skills_raw if s]
        elif isinstance(skills_raw, str):
            all_skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
        elif isinstance(skills_raw, dict):
            # Flatten all sub-categories into one list
            for category_items in skills_raw.values():
                if isinstance(category_items, list):
                    all_skills.extend([str(s).strip() for s in category_items if s])
                elif isinstance(category_items, str):
                    all_skills.append(category_items.strip())
        if all_skills:
            record.skills = all_skills

        # Links — top-level or nested under 'contact'
        links = data.get("links") or {}
        if isinstance(links, dict):
            record.links = {k: str(v) for k, v in links.items() if v}
        # Also check top-level and contact-level GitHub / LinkedIn
        github = data.get("github") or data.get("github_url") or contact.get("github") or contact.get("github_url")
        if github:
            record.links["github"] = str(github)
        linkedin = data.get("linkedin") or data.get("linkedin_url") or contact.get("linkedin") or contact.get("linkedin_url")
        if linkedin:
            record.links["linkedin"] = str(linkedin)

        # Experience — support 'workExperience', start/end aliases, role, summary
        exp_list = data.get("experience") or data.get("workExperience") or data.get("work_experience") or []
        if isinstance(exp_list, list):
            for exp in exp_list:
                if isinstance(exp, dict):
                    record.experience.append({
                        "company": exp.get("company", ""),
                        "title": exp.get("title", "") or exp.get("role", ""),
                        "start_date": exp.get("start_date") or exp.get("start"),
                        "end_date": exp.get("end_date") or exp.get("end"),
                        "is_current": exp.get("is_current", exp.get("end") is None),
                        "description": (
                            " ".join(exp["description"]) if isinstance(exp.get("description"), list)
                            else exp.get("description") or exp.get("summary") or ""
                        ),
                    })

        # Education
        edu_list = data.get("education") or []
        if isinstance(edu_list, list):
            for edu in edu_list:
                if isinstance(edu, dict):
                    record.education.append({
                        "institution": edu.get("institution", ""),
                        "degree": edu.get("degree", ""),
                        "field_of_study": edu.get("field_of_study", edu.get("field", "")),
                        "start_date": edu.get("start_date"),
                        "end_date": edu.get("end_date"),
                    })

        logger.debug("ingest", self.source_name, f"Parsed candidate: {record.full_name}")
        return record

    def _safe_str(self, data, key):
        """Safely get a string value from a dict, returning None for missing/null."""
        val = data.get(key)
        if val is None:
            return None
        return str(val).strip() or None
