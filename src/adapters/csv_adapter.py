"""
CSV Adapter — extracts candidate data from recruiter CSV files.

Handles: valid CSV, empty CSV, missing columns, encoding issues.
"""

import csv
import os
from src.adapters.base_adapter import BaseAdapter
from src.schema.source_record import SourceRecord
from src.logger import logger


class CsvAdapter(BaseAdapter):
    """Adapter for recruiter CSV files."""

    def __init__(self):
        super().__init__()
        self.source_name = "recruiter_csv"
        self.supported_extensions = [".csv"]

    def extract(self, input_data):
        """
        Extract candidate data from a CSV file.

        Args:
            input_data: Path to the CSV file.

        Returns:
            list[SourceRecord] — one per row, or empty list on failure.
        """
        records = []

        # Validate file exists
        if not input_data or not os.path.exists(input_data):
            logger.warning("ingest", self.source_name, f"File not found: {input_data}")
            return [self._empty_record_with_error(f"File not found: {input_data}")]

        # Check if file is empty
        if os.path.getsize(input_data) == 0:
            logger.warning("ingest", self.source_name, "CSV file is empty")
            return [self._empty_record_with_error("CSV file is empty")]

        try:
            with open(input_data, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)

                if not reader.fieldnames:
                    logger.warning("ingest", self.source_name, "CSV has no headers")
                    return [self._empty_record_with_error("CSV has no headers")]

                for row_num, row in enumerate(reader, start=1):
                    try:
                        record = self._parse_row(row)
                        records.append(record)
                    except Exception as e:
                        logger.warning(
                            "ingest", self.source_name,
                            f"Skipping row {row_num}: {str(e)}"
                        )

        except Exception as e:
            logger.error("ingest", self.source_name, f"Failed to read CSV: {str(e)}")
            return [self._empty_record_with_error(f"Failed to read CSV: {str(e)}")]

        if not records:
            logger.warning("ingest", self.source_name, "CSV produced no valid records")
            return [self._empty_record_with_error("CSV produced no valid records")]

        logger.info("ingest", self.source_name, f"Extracted {len(records)} records from CSV")
        return records

    def _parse_row(self, row):
        """Parse a single CSV row into a SourceRecord."""
        record = SourceRecord(
            source_name=self.source_name,
            extraction_method="structured",
        )

        # Map common CSV column names to our fields (case-insensitive)
        mapped = {k.lower().strip(): v.strip() if v else "" for k, v in row.items()}

        # Name
        record.full_name = (
            mapped.get("full_name")
            or mapped.get("name")
            or mapped.get("candidate_name")
            or self._join_name(mapped.get("first_name", ""), mapped.get("last_name", ""))
        ) or None

        # Emails
        email = mapped.get("email") or mapped.get("email_address") or ""
        if email:
            record.emails = [e.strip() for e in email.split(";") if e.strip()]

        # Phones
        phone = mapped.get("phone") or mapped.get("phone_number") or mapped.get("mobile") or ""
        if phone:
            record.phones = [p.strip() for p in phone.split(";") if p.strip()]

        # Location
        record.location = mapped.get("location") or mapped.get("city") or None

        # Headline / Title
        record.headline = mapped.get("headline") or mapped.get("title") or mapped.get("current_title") or None

        # Years experience
        yoe = mapped.get("years_experience") or mapped.get("experience_years") or mapped.get("yoe")
        if yoe:
            try:
                record.years_experience = float(yoe)
            except ValueError:
                record.errors.append(f"Invalid years_experience: {yoe}")

        # Skills — support multiple common column names
        # Collect from all skill-related columns and merge them
        skill_columns = ["skills", "skill_list", "core_skills", "technical_skills", "languages", "tools"]
        all_skills = []
        for col in skill_columns:
            raw = mapped.get(col, "")
            if raw:
                all_skills.extend([s.strip() for s in raw.replace("|", ",").split(",") if s.strip()])
        if all_skills:
            record.skills = all_skills

        # Links
        github = mapped.get("github") or mapped.get("github_url") or ""
        linkedin = mapped.get("linkedin") or mapped.get("linkedin_url") or ""
        if github:
            record.links["github"] = github
        if linkedin:
            record.links["linkedin"] = linkedin

        return record

    def _join_name(self, first, last):
        """Join first and last name, handling empty values."""
        parts = [p.strip() for p in [first, last] if p and p.strip()]
        return " ".join(parts) if parts else ""
