"""
TXT Adapter — extracts candidate data from recruiter notes text files.

Handles: empty files, unstructured freeform text.
Uses regex and heuristics to find candidate info in notes.
"""

import os
import re
from src.adapters.base_adapter import BaseAdapter
from src.schema.source_record import SourceRecord
from src.logger import logger


class TxtAdapter(BaseAdapter):
    """Adapter for recruiter notes TXT files."""

    def __init__(self):
        super().__init__()
        self.source_name = "recruiter_notes"
        self.supported_extensions = [".txt"]

    def extract(self, input_data):
        """Extract candidate data from a text file of recruiter notes."""
        if not input_data or not os.path.exists(input_data):
            logger.warning("ingest", self.source_name, f"File not found: {input_data}")
            return [self._empty_record_with_error(f"File not found: {input_data}")]

        if os.path.getsize(input_data) == 0:
            logger.warning("ingest", self.source_name, "TXT file is empty")
            return [self._empty_record_with_error("TXT file is empty")]

        try:
            with open(input_data, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except Exception as e:
            logger.error("ingest", self.source_name, f"Failed to read TXT: {str(e)}")
            return [self._empty_record_with_error(f"Failed to read TXT: {str(e)}")]

        if not text.strip():
            logger.warning("ingest", self.source_name, "TXT file is empty after reading")
            return [self._empty_record_with_error("TXT file is empty")]

        record = self._parse_notes(text)
        record.raw_text = text
        logger.info("ingest", self.source_name, f"Extracted notes ({len(text)} chars)")
        return [record]

    def _parse_notes(self, text):
        """Parse recruiter notes using regex heuristics."""
        record = SourceRecord(
            source_name=self.source_name,
            extraction_method="heuristic",
        )

        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        record.emails = list(set(re.findall(email_pattern, text)))

        # Extract phone numbers
        phone_pattern = r'[\+]?[\d\s\-\(\)]{7,15}'
        raw_phones = re.findall(phone_pattern, text)
        record.phones = [p.strip() for p in raw_phones if len(re.sub(r'\D', '', p)) >= 7]

        # Look for name patterns in notes
        name_patterns = [
            r'(?:candidate|name|applicant)[:\s]+([A-Z][a-z]+(?:[^\S\n][A-Z][a-z]+)+)',
            r'(?:spoke with|interviewed|met with)[^\S\n]+([A-Z][a-z]+(?:[^\S\n][A-Z][a-z]+)+)',
        ]
        for pattern in name_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                record.full_name = match.group(1).strip()
                break

        # Look for years of experience mentions
        yoe_patterns = [
            r'(\d+)\+?\s*(?:years?|yrs?)\s*(?:of\s*)?(?:experience|exp)',
            r'(?:experience|exp)[:\s]*(\d+)\+?\s*(?:years?|yrs?)',
        ]
        for pattern in yoe_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    record.years_experience = float(match.group(1))
                except ValueError:
                    pass
                break

        # Look for skills mentions
        skills_patterns = [
            r'(?:skills?|technologies?|stack)[:\s]+([^\n]+)',
            r'(?:proficient|experienced|skilled)\s+(?:in|with)\s+([^\n.]+)',
        ]
        for pattern in skills_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                skills_str = match.group(1)
                skills = re.split(r'[,;|]', skills_str)
                record.skills = [s.strip() for s in skills if s.strip() and len(s.strip()) < 50]
                break

        # Location
        loc_patterns = [
            r'(?:location|based in|located in|from)[:\s]+([^\n.,]+(?:,\s*[^\n.]+)?)',
        ]
        for pattern in loc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                record.location = match.group(1).strip()
                break

        # Links
        url_pattern = r'https?://[^\s<>\"\')\]]*'
        urls = re.findall(url_pattern, text)
        for url in urls:
            lower = url.lower()
            if "github.com" in lower:
                record.links["github"] = url
            elif "linkedin.com" in lower:
                record.links["linkedin"] = url

        return record
