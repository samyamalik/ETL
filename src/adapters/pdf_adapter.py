"""
PDF Adapter — extracts candidate data from resume PDF files.

Uses pdfplumber for text extraction. Does NOT do OCR.
Handles: corrupted PDF, empty pages, scanned-image PDFs (skips with warning).
"""

import os
import re
from src.adapters.base_adapter import BaseAdapter
from src.schema.source_record import SourceRecord
from src.logger import logger


class PdfAdapter(BaseAdapter):
    """Adapter for resume PDF files."""

    def __init__(self):
        super().__init__()
        self.source_name = "resume_pdf"
        self.supported_extensions = [".pdf"]

    def extract(self, input_data):
        """Extract candidate data from a PDF resume."""
        if not input_data or not os.path.exists(input_data):
            logger.warning("ingest", self.source_name, f"File not found: {input_data}")
            return [self._empty_record_with_error(f"File not found: {input_data}")]

        if os.path.getsize(input_data) == 0:
            logger.warning("ingest", self.source_name, "PDF file is empty")
            return [self._empty_record_with_error("PDF file is empty")]

        # Try to extract text from PDF
        try:
            import pdfplumber
            text = ""
            with pdfplumber.open(input_data) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
        except Exception as e:
            logger.error("ingest", self.source_name, f"Failed to read PDF: {str(e)}")
            return [self._empty_record_with_error(f"Failed to read PDF: {str(e)}")]

        if not text.strip():
            logger.warning("ingest", self.source_name, "PDF contains no extractable text (may be scanned)")
            return [self._empty_record_with_error("No extractable text in PDF")]

        record = self._parse_text(text)
        record.raw_text = text
        logger.info("ingest", self.source_name, f"Extracted text from PDF ({len(text)} chars)")
        return [record]

    def _parse_text(self, text):
        """Parse raw text from a resume PDF using regex and heuristics."""
        record = SourceRecord(
            source_name=self.source_name,
            extraction_method="regex",
        )

        # Extract emails
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        record.emails = list(set(re.findall(email_pattern, text)))

        # Extract phone numbers
        phone_pattern = r'[\+]?[\d\s\-\(\)]{7,15}'
        raw_phones = re.findall(phone_pattern, text)
        record.phones = [p.strip() for p in raw_phones if len(re.sub(r'\D', '', p)) >= 7]

        # Extract name — usually the first non-empty line
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if lines:
            first_line = lines[0]
            # Name heuristic: first line that is short and doesn't look like a header
            if len(first_line) < 60 and not re.search(r'(resume|curriculum|vitae|cv)', first_line, re.IGNORECASE):
                record.full_name = first_line

        # Extract links
        url_pattern = r'https?://[^\s<>\"\')\]]*'
        urls = re.findall(url_pattern, text)
        for url in urls:
            lower = url.lower()
            if "github.com" in lower:
                record.links["github"] = url
            elif "linkedin.com" in lower:
                record.links["linkedin"] = url
            else:
                record.links.setdefault("other", [])
                if isinstance(record.links.get("other"), list):
                    record.links["other"].append(url)

        # Extract skills — look for a "Skills" section
        skills_text = self._extract_section(text, ["skills", "technical skills", "technologies"])
        if skills_text:
            # Split by common delimiters
            skills = re.split(r'[,|•·\n]', skills_text)
            record.skills = [s.strip() for s in skills if s.strip() and len(s.strip()) < 50]

        # Extract location — look for common patterns
        location_patterns = [
            r'(?:location|address|city)[:\s]*([^\n]+)',
            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z]{2})',  # City, ST
            r'([A-Z][a-z]+(?:\s[A-Z][a-z]+)*,\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)*)',  # City, State/Country
        ]
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                record.location = match.group(1).strip()
                break

        return record

    def _extract_section(self, text, section_names):
        """Extract text from a named section of the resume."""
        lines = text.split("\n")
        capturing = False
        captured = []

        # Common section headers that signal end of current section
        all_headers = [
            "skills", "technical skills", "technologies",
            "experience", "work experience", "employment",
            "education", "projects", "certifications",
            "summary", "objective", "references", "awards",
        ]

        for line in lines:
            stripped = line.strip().lower()

            # Check if this line starts a target section
            if not capturing:
                for name in section_names:
                    if stripped.startswith(name) or stripped == name:
                        capturing = True
                        # Don't include the header itself
                        remainder = stripped[len(name):].strip(": ")
                        if remainder:
                            captured.append(remainder)
                        break
            else:
                # Check if we've hit a new section
                is_new_section = False
                for header in all_headers:
                    if header not in section_names and (stripped.startswith(header) or stripped == header):
                        is_new_section = True
                        break
                if is_new_section:
                    break
                if line.strip():
                    captured.append(line.strip())

        return " ".join(captured)
