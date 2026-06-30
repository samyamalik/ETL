"""Edge case tests — testing every edge case from the requirements."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from src.pipeline import process_candidate
from src.adapters.csv_adapter import CsvAdapter
from src.adapters.ats_json_adapter import AtsJsonAdapter
from src.adapters.txt_adapter import TxtAdapter
from src.projection.config_schema import load_output_config
from src.errors import ConfigError

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIXTURES = os.path.join(PROJECT_ROOT, "tests", "fixtures")
os.makedirs(FIXTURES, exist_ok=True)

def _write(name, content):
    path = os.path.join(FIXTURES, name)
    with open(path, "w") as f:
        f.write(content)
    return path

# ── File-level edge cases ──

class TestEmptyFiles:
    def test_empty_csv(self):
        path = _write("edge_empty.csv", "")
        records = CsvAdapter().extract(path)
        assert records[0].errors

    def test_empty_json(self):
        path = _write("edge_empty.json", "")
        records = AtsJsonAdapter().extract(path)
        assert records[0].errors

    def test_empty_txt(self):
        path = _write("edge_empty.txt", "")
        records = TxtAdapter().extract(path)
        assert records[0].errors

class TestInvalidFiles:
    def test_invalid_json(self):
        path = _write("edge_bad.json", "{invalid json content!!!")
        records = AtsJsonAdapter().extract(path)
        assert records[0].errors

    def test_missing_file(self):
        records = CsvAdapter().extract("/does/not/exist.csv")
        assert records[0].errors

class TestMissingSource:
    def test_missing_github(self):
        """Pipeline should survive missing GitHub profile."""
        result = process_candidate({"github_profile": "nonexistent_user_xyz_12345"})
        # Should have errors but not crash
        assert isinstance(result["errors"], list)

class TestDuplicateCandidates:
    def test_same_email_multiple_sources(self):
        csv_path = _write("edge_dup.csv", "full_name,email\nJohn Doe,john@example.com\n")
        json_path = _write("edge_dup.json", json.dumps({"full_name": "John Doe", "email": "john@example.com"}))
        result = process_candidate({"recruiter_csv": csv_path, "ats_json": json_path})
        emails = [e["address"] for e in result["output"]["emails"]]
        assert emails.count("john@example.com") == 1  # Deduped

    def test_different_names_same_person(self):
        csv_path = _write("edge_name1.csv", "full_name,email\nJohnny Doe,john@example.com\n")
        json_path = _write("edge_name2.json", json.dumps({"full_name": "John Doe", "email": "john@example.com"}))
        result = process_candidate({"recruiter_csv": csv_path, "ats_json": json_path})
        assert result["output"]["full_name"] == "John Doe"  # ATS wins

class TestPhoneEdgeCases:
    def test_various_formats(self):
        data = {"full_name": "Test", "phones": ["+1-555-123-4567", "(555) 123 4567", "5551234567"]}
        path = _write("edge_phones.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        phones = result["output"].get("phones", [])
        assert len(phones) >= 1

    def test_invalid_phone(self):
        data = {"full_name": "Test", "phones": ["123"]}
        path = _write("edge_bad_phone.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        # Invalid phone should be filtered out — phones key will be None or empty list in default config
        phones = result["output"].get("phones")
        assert phones is None or phones == []

class TestSkillEdgeCases:
    def test_skill_aliases(self):
        data = {"full_name": "Test", "skills": ["js", "reactjs", "nodejs"]}
        path = _write("edge_skills.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        skill_names = [s["name"] for s in result["output"]["skills"]]
        assert "javascript" in skill_names
        assert "react" in skill_names
        assert "node.js" in skill_names

    def test_duplicate_skills(self):
        data = {"full_name": "Test", "skills": ["Python", "python", "PYTHON"]}
        path = _write("edge_dup_skills.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        skill_names = [s["name"] for s in result["output"]["skills"]]
        assert skill_names.count("python") == 1

class TestConfigEdgeCases:
    def test_invalid_config(self):
        result = process_candidate(
            {"ats_json": _write("edge_cfg.json", json.dumps({"full_name": "Test"}))},
            output_config={"version": "1.0", "missing_value_strategy": "BAD"}
        )
        assert not result["is_valid"]

    def test_unknown_canonical_path(self):
        with pytest.raises(ConfigError):
            load_output_config(config_dict={
                "version": "1.0",
                "fields": [{"canonical_path": "nonexistent", "output_name": "x"}]
            })

class TestMissingData:
    def test_missing_education(self):
        data = {"full_name": "Test", "email": "test@example.com"}
        path = _write("edge_no_edu.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        # Empty list is treated as missing in on_missing=null strategy → projected as null
        edu = result["output"].get("education")
        assert edu is None or edu == []

    def test_missing_dates(self):
        data = {"full_name": "Test", "experience": [{"company": "Acme", "title": "Dev"}]}
        path = _write("edge_no_dates.json", json.dumps(data))
        result = process_candidate({"ats_json": path})
        assert result["output"]["experience"][0]["start_date"] is None

class TestNoSources:
    def test_no_sources(self):
        result = process_candidate({})
        assert not result["is_valid"]
        assert result["errors"]
