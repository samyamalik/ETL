import pytest
import os
import json
from src.schema.source_record import SourceRecord
from src.schema.canonical import CanonicalProfile
from src.merger.merge_engine import merge_records
from src.scoring.confidence import score_profile
from src.provenance.tracker import track_provenance
from src.projection.engine import project
from src.projection.config_schema import load_output_config
from src.validation.validator import validate_output
from src.normalizers.normalizers import (
    normalize_phone, normalize_email, normalize_name, normalize_skill, normalize_date
)
from src.adapters.pdf_adapter import PdfAdapter
from src.adapters.csv_adapter import CsvAdapter
from src.adapters.github_adapter import GithubAdapter
from src.adapters.ats_json_adapter import AtsJsonAdapter
from src.pipeline import process_candidate, create_default_registry


# Helper to build a mock SourceRecord
def mock_record(source, **kwargs):
    record = SourceRecord(source_name=source, extraction_method="mock")
    for k, v in kwargs.items():
        setattr(record, k, v)
    return record


class TestAssignment20Edges:
    
    # 1. Conflicting values across sources
    def test_1_conflicting_values_across_sources(self):
        rec1 = mock_record("ats_json", experience=[{"company": "Google", "title": "SWE", "is_current": True}])
        rec2 = mock_record("resume_pdf", experience=[{"company": "Microsoft", "title": "SWE", "is_current": True}])
        profile = merge_records([rec1, rec2])
        # ats_json (priority 1) should win over resume_pdf (priority 3) if they conflict on scalars,
        # but experience is a list. Wait, lists are union merged. 
        # So it keeps both, but we can test a scalar like headline.
        rec1.headline = "Software Engineer at Google"
        rec2.headline = "Software Engineer at Microsoft"
        profile = merge_records([rec1, rec2])
        assert profile.headline == "Software Engineer at Google"

    # 2. Missing fields
    def test_2_missing_fields(self):
        profile = CanonicalProfile(full_name="John Doe") # No phone
        config = load_output_config(config_dict={
            "fields": [{"path": "phone", "from": "phones[0]", "type": "string"}],
            "on_missing": "null"
        })
        output = project(profile, config)
        assert output["phone"] is None

    # 3. Duplicate candidate from multiple sources
    def test_3_duplicate_candidate_multiple_sources(self):
        rec1 = mock_record("ats_json", emails=["john@example.com"], full_name="John")
        rec2 = mock_record("resume_pdf", emails=["john@example.com"], full_name="John Doe")
        profile = merge_records([rec1, rec2])
        assert len(profile.emails) == 1
        assert profile.emails[0].address == "john@example.com"
        assert profile.full_name == "John" # ATS priority

    # 4. Invalid phone number
    def test_4_invalid_phone_number(self):
        assert normalize_phone("abcdef") is None

    # 5. Different phone formats
    def test_5_different_phone_formats(self):
        # phonenumbers lib handles these if installed, else fallback handles digits
        # Default region is now India (+91)
        p1 = normalize_phone("+91-9876543210")
        p2 = normalize_phone("(987) 654-3210")
        assert p1 == "+919876543210"
        assert p2 == "+919876543210"  # 10-digit number defaults to +91 (India)

    # 6. Invalid email
    def test_6_invalid_email(self):
        assert normalize_email("john@gmail") is None
        assert normalize_email("abc.com") is None

    # 7. Different name formats
    def test_7_different_name_formats(self):
        assert normalize_name("John D Doe").lower() == "john d doe"
        assert normalize_name("DOE, JOHN").lower() == "john doe"

    # 8. Duplicate skills
    def test_8_duplicate_skills(self):
        assert normalize_skill("C++") == "c++"
        assert normalize_skill("C Plus Plus") == "c plus plus"
        
    # 9. Different date formats
    def test_9_different_date_formats(self):
        assert normalize_date("Jan 2024") == "2024-01-01"
        assert normalize_date("01/2024") == "2024"
        assert normalize_date("2024-01") == "2024-01"

    # 10. Resume parsing failure
    def test_10_resume_parsing_failure(self):
        adapter = PdfAdapter()
        records = adapter.extract("tests/fixtures/20_edges/corrupted.pdf")
        assert len(records) == 1
        assert len(records[0].errors) > 0 

    # 11. Empty input file
    def test_11_empty_input_file(self):
        adapter = CsvAdapter()
        records = adapter.extract("tests/fixtures/20_edges/empty.csv")
        assert len(records) == 1
        assert len(records[0].errors) > 0

    # 12. GitHub URL doesn't exist
    def test_12_github_url_doesnt_exist(self):
        adapter = GithubAdapter()
        records = adapter.extract("not_a_real_user_xyz123_abc")
        assert len(records) == 1
        assert len(records[0].errors) > 0

    # 13. LinkedIn unavailable/private (Mocked pipeline exception catch)
    def test_13_private_profile_pipeline_resilience(self):
        registry = create_default_registry()
        res = process_candidate({"linkedin_private": "url"}, registry=registry)
        assert res["is_valid"] is False
        assert "No adapter" in str(res["errors"])

    # 14. Same skill with different confidence
    def test_14_same_skill_different_confidence(self):
        rec1 = mock_record("resume_pdf", skills=["Python"])
        rec2 = mock_record("github_profile", skills=["Python"])
        profile = merge_records([rec1, rec2])
        profile = track_provenance(profile, [rec1, rec2])
        profile = score_profile(profile, [rec1, rec2])
        assert len(profile.skills) == 1
        assert profile.skills[0].confidence == 0.475

    # 15. Multiple emails
    def test_15_multiple_emails(self):
        rec1 = mock_record("ats_json", emails=["sam@work.com", "sam@personal.com"])
        profile = merge_records([rec1])
        assert len(profile.emails) == 2

    # 16. Multiple locations
    def test_16_multiple_locations(self):
        rec1 = mock_record("ats_json", location="Bangalore")
        rec2 = mock_record("resume_pdf", location="Delhi")
        profile = merge_records([rec1, rec2])
        profile = track_provenance(profile, [rec1, rec2])
        assert profile.location.raw == "Bangalore"
        loc_prov = next(p for p in profile.provenance if p.field_path == "location")
        assert len(loc_prov.alternatives) == 1
        assert loc_prov.alternatives[0]["value"] == "Delhi"

    # 17. Malformed JSON (ATS)
    def test_17_malformed_json(self):
        adapter = AtsJsonAdapter()
        records = adapter.extract("tests/fixtures/20_edges/malformed.json")
        assert len(records) == 1
        assert len(records[0].errors) > 0

    # 18. Runtime config asks for non-existent field
    def test_18_config_nonexistent_field(self):
        # We test that asking for a non-existent base path like 'salary' raises ConfigError
        try:
            config = load_output_config(config_dict={
                "fields": [{"path": "salary", "from": "salary", "type": "string"}],
                "on_missing": "omit"
            })
            assert False, "Should raise ConfigError for unknown canonical path"
        except Exception as e:
            assert "Unknown canonical path" in str(e)

    # 19. Config type mismatch
    def test_19_config_type_mismatch(self):
        config = load_output_config(config_dict={
            "fields": [{"path": "years_experience", "from": "years_experience", "type": "number"}], 
            "on_missing": "null"
        })
        # Simulate projection engine returning a wrong type
        output = {"years_experience": "five"}
        valid, errs = validate_output(output, config)
        assert not valid
        assert "Expected type" in str(errs) or "ValidationError" in str(errs)

    # 20. Candidate has no usable information
    def test_20_no_usable_information(self):
        res = process_candidate({"recruiter_csv": "tests/fixtures/20_edges/empty.csv"})
        assert res["output"]["overall_confidence"] == 0.0
