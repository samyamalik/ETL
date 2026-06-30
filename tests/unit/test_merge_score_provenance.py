"""
Unit tests for merge engine, confidence scoring, and provenance tracking.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.schema.source_record import SourceRecord
from src.merger.merge_engine import merge_records
from src.scoring.confidence import score_profile
from src.provenance.tracker import track_provenance

def _make_record(source_name, **kwargs):
    return SourceRecord(source_name=source_name, **kwargs)

class TestMergeEngine:
    def test_single_source(self):
        records = [_make_record("ats_json", full_name="John Doe", emails=["john@example.com"])]
        profile = merge_records(records)
        assert profile.full_name == "John Doe"
        assert len(profile.emails) == 1

    def test_priority_resolution(self):
        records = [
            _make_record("recruiter_csv", full_name="Johnny Doe", headline="Dev"),
            _make_record("ats_json", full_name="John Doe", headline="Senior Dev"),
        ]
        profile = merge_records(records)
        assert profile.full_name == "John Doe"
        assert profile.headline == "Senior Dev"

    def test_email_union(self):
        records = [
            _make_record("ats_json", emails=["john@a.com"]),
            _make_record("recruiter_csv", emails=["john@a.com", "john@b.com"]),
        ]
        profile = merge_records(records)
        addresses = [e.address for e in profile.emails]
        assert "john@a.com" in addresses
        assert "john@b.com" in addresses

    def test_skill_dedup(self):
        records = [
            _make_record("ats_json", skills=["Python", "React"]),
            _make_record("recruiter_csv", skills=["python", "Java"]),
        ]
        profile = merge_records(records)
        skill_names = [s.name for s in profile.skills]
        assert skill_names.count("python") == 1
        assert "react" in skill_names

    def test_empty_records(self):
        profile = merge_records([])
        assert profile.full_name == ""

    def test_deterministic_id(self):
        records = [_make_record("ats_json", full_name="John Doe", emails=["john@example.com"])]
        p1 = merge_records(records)
        p2 = merge_records(records)
        assert p1.candidate_id == p2.candidate_id

    def test_null_fallthrough(self):
        records = [
            _make_record("ats_json", full_name="John", headline=None),
            _make_record("recruiter_csv", full_name="Johnny", headline="Software Engineer"),
        ]
        profile = merge_records(records)
        assert profile.full_name == "John"
        assert profile.headline == "Software Engineer"

    def test_experience_dedup(self):
        exp = {"company": "Google", "title": "Engineer", "start_date": "2020-01"}
        records = [_make_record("ats_json", experience=[exp]), _make_record("recruiter_csv", experience=[exp])]
        profile = merge_records(records)
        assert len(profile.experience) == 1

class TestConfidenceScoring:
    def test_basic_scoring(self):
        records = [_make_record("ats_json", full_name="John Doe", emails=["john@example.com"], extraction_method="structured")]
        profile = merge_records(records)
        profile = score_profile(profile, records)
        assert 0.0 <= profile.overall_confidence <= 1.0

    def test_higher_trust(self):
        r_ats = [_make_record("ats_json", full_name="John", extraction_method="structured")]
        r_notes = [_make_record("recruiter_notes", full_name="John", extraction_method="heuristic")]
        p_ats = score_profile(merge_records(r_ats), r_ats)
        p_notes = score_profile(merge_records(r_notes), r_notes)
        assert p_ats.overall_confidence >= p_notes.overall_confidence

    def test_empty_profile(self):
        records = [_make_record("ats_json")]
        profile = score_profile(merge_records(records), records)
        assert profile.overall_confidence == 0.0

    def test_confidence_range(self):
        records = [_make_record("ats_json", full_name="John", emails=["j@e.com"], skills=["Python"], extraction_method="structured")]
        profile = score_profile(merge_records(records), records)
        assert 0.0 <= profile.overall_confidence <= 1.0
        for e in profile.emails:
            assert 0.0 <= e.confidence <= 1.0

class TestProvenance:
    def test_entries_created(self):
        records = [_make_record("ats_json", full_name="John", emails=["j@e.com"], extraction_method="structured")]
        profile = track_provenance(score_profile(merge_records(records), records), records)
        assert len(profile.provenance) > 0

    def test_has_source(self):
        records = [_make_record("ats_json", full_name="John", extraction_method="structured")]
        profile = track_provenance(score_profile(merge_records(records), records), records)
        name_prov = [p for p in profile.provenance if p.field_path == "full_name"]
        assert len(name_prov) == 1
        assert name_prov[0].source == "ats_json"

    def test_alternatives(self):
        records = [
            _make_record("ats_json", full_name="John Doe", extraction_method="structured"),
            _make_record("recruiter_csv", full_name="Johnny Doe", extraction_method="structured"),
        ]
        profile = track_provenance(score_profile(merge_records(records), records), records)
        name_prov = [p for p in profile.provenance if p.field_path == "full_name"]
        assert len(name_prov[0].alternatives) >= 1

    def test_timestamp(self):
        records = [_make_record("ats_json", full_name="John", extraction_method="structured")]
        profile = track_provenance(score_profile(merge_records(records), records), records)
        for entry in profile.provenance:
            assert entry.timestamp
