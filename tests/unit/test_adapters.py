"""
Unit tests for source adapters — CSV and ATS JSON adapters.
"""

import sys
import os
import json
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.adapters.csv_adapter import CsvAdapter
from src.adapters.ats_json_adapter import AtsJsonAdapter
from src.adapters.txt_adapter import TxtAdapter

# Use project root for temp files
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEMP_DIR = os.path.join(PROJECT_ROOT, "tests", "fixtures")
os.makedirs(TEMP_DIR, exist_ok=True)


def _write_temp(filename, content):
    """Write content to a temp file in fixtures dir."""
    path = os.path.join(TEMP_DIR, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


# ──────────────────────────────────────────────
#  CSV ADAPTER TESTS
# ──────────────────────────────────────────────

class TestCsvAdapter:
    def setup_method(self):
        self.adapter = CsvAdapter()

    def test_valid_csv(self):
        path = _write_temp("test_valid.csv",
            "full_name,email,phone,location,skills\n"
            "John Doe,john@example.com,555-1234,NYC,\"Python,Java\"\n"
        )
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].full_name == "John Doe"
        assert "john@example.com" in records[0].emails
        assert records[0].source_name == "recruiter_csv"

    def test_empty_csv(self):
        path = _write_temp("test_empty.csv", "")
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].errors  # Should have an error

    def test_header_only_csv(self):
        path = _write_temp("test_header_only.csv", "name,email,phone\n")
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].errors  # No valid records

    def test_missing_file(self):
        records = self.adapter.extract("/nonexistent/path.csv")
        assert len(records) == 1
        assert records[0].errors

    def test_can_handle(self):
        assert self.adapter.can_handle("data.csv") is True
        assert self.adapter.can_handle("data.json") is False
        assert self.adapter.can_handle("") is False

    def test_multiple_rows(self):
        path = _write_temp("test_multi.csv",
            "full_name,email\n"
            "Alice,alice@example.com\n"
            "Bob,bob@example.com\n"
        )
        records = self.adapter.extract(path)
        assert len(records) == 2

    def test_semicolon_emails(self):
        path = _write_temp("test_multi_email.csv",
            "full_name,email\n"
            "Alice,alice@a.com;alice@b.com\n"
        )
        records = self.adapter.extract(path)
        assert len(records[0].emails) == 2


# ──────────────────────────────────────────────
#  ATS JSON ADAPTER TESTS
# ──────────────────────────────────────────────

class TestAtsJsonAdapter:
    def setup_method(self):
        self.adapter = AtsJsonAdapter()

    def test_valid_single_candidate(self):
        data = {"full_name": "Jane Smith", "email": "jane@example.com", "skills": ["Python", "SQL"]}
        path = _write_temp("test_valid.json", json.dumps(data))
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].full_name == "Jane Smith"
        assert "jane@example.com" in records[0].emails
        assert "Python" in records[0].skills

    def test_valid_candidate_list(self):
        data = [
            {"full_name": "Alice", "email": "alice@example.com"},
            {"full_name": "Bob", "email": "bob@example.com"},
        ]
        path = _write_temp("test_list.json", json.dumps(data))
        records = self.adapter.extract(path)
        assert len(records) == 2

    def test_wrapper_format(self):
        data = {"candidates": [{"full_name": "Charlie", "email": "charlie@example.com"}]}
        path = _write_temp("test_wrapper.json", json.dumps(data))
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].full_name == "Charlie"

    def test_invalid_json(self):
        path = _write_temp("test_invalid.json", "{bad json")
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].errors

    def test_empty_json(self):
        path = _write_temp("test_empty.json", "")
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].errors

    def test_missing_file(self):
        records = self.adapter.extract("/nonexistent/path.json")
        assert len(records) == 1
        assert records[0].errors

    def test_nested_location(self):
        data = {"full_name": "Test", "location": {"city": "NYC", "state": "NY", "country": "US"}}
        path = _write_temp("test_nested_loc.json", json.dumps(data))
        records = self.adapter.extract(path)
        assert "NYC" in records[0].location

    def test_experience_parsing(self):
        data = {
            "full_name": "Test",
            "experience": [
                {"company": "Acme", "title": "Dev", "start_date": "2020-01", "end_date": "Present"}
            ]
        }
        path = _write_temp("test_exp.json", json.dumps(data))
        records = self.adapter.extract(path)
        assert len(records[0].experience) == 1
        assert records[0].experience[0]["company"] == "Acme"


# ──────────────────────────────────────────────
#  TXT ADAPTER TESTS
# ──────────────────────────────────────────────

class TestTxtAdapter:
    def setup_method(self):
        self.adapter = TxtAdapter()

    def test_valid_notes(self):
        path = _write_temp("test_notes.txt",
            "Candidate: John Doe\n"
            "Email: john@example.com\n"
            "Phone: 555-123-4567\n"
            "Skills: Python, JavaScript, React\n"
            "Location: Based in San Francisco\n"
            "He has 5 years of experience.\n"
        )
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].full_name == "John Doe"
        assert "john@example.com" in records[0].emails
        assert records[0].years_experience == 5.0
        assert len(records[0].skills) > 0

    def test_empty_file(self):
        path = _write_temp("test_empty.txt", "")
        records = self.adapter.extract(path)
        assert len(records) == 1
        assert records[0].errors

    def test_missing_file(self):
        records = self.adapter.extract("/nonexistent/path.txt")
        assert len(records) == 1
        assert records[0].errors

    def test_can_handle(self):
        assert self.adapter.can_handle("notes.txt") is True
        assert self.adapter.can_handle("data.csv") is False
