"""Integration test — full pipeline end-to-end with sample data."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.pipeline import process_candidate

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "sample_data")

class TestFullPipeline:
    def test_full_pipeline_sample_data(self):
        sources = {
            "recruiter_csv": os.path.join(SAMPLE_DIR, "candidates.csv"),
            "ats_json": os.path.join(SAMPLE_DIR, "ats_data.json"),
            "recruiter_notes": os.path.join(SAMPLE_DIR, "recruiter_notes.txt"),
        }
        result = process_candidate(sources)
        assert result["is_valid"]
        assert result["output"]
        assert result["candidate_id"]
        assert result["output"]["full_name"] == "Priya Sharma"
        assert len(result["output"]["emails"]) >= 1
        assert len(result["output"]["skills"]) >= 5
        assert len(result["output"]["experience"]) >= 1

    def test_determinism(self):
        """Same inputs should produce identical output every time."""
        sources = {
            "ats_json": os.path.join(SAMPLE_DIR, "ats_data.json"),
            "recruiter_notes": os.path.join(SAMPLE_DIR, "recruiter_notes.txt"),
        }
        r1 = process_candidate(sources)
        r2 = process_candidate(sources)
        assert r1["candidate_id"] == r2["candidate_id"]
        assert r1["output"]["full_name"] == r2["output"]["full_name"]

    def test_custom_config(self):
        sources = {"ats_json": os.path.join(SAMPLE_DIR, "ats_data.json")}
        config = {
            "version": "1.0",
            "fields": [
                {"canonical_path": "full_name", "output_name": "name"},
                {"canonical_path": "skills", "output_name": "skills"},
            ],
            "include_provenance": False,
            "include_confidence": False,
            "missing_value_strategy": "omit",
        }
        result = process_candidate(sources, output_config=config)
        assert result["is_valid"]
        assert "name" in result["output"]
        assert "full_name" not in result["output"]

    def test_single_source_pipeline(self):
        sources = {"ats_json": os.path.join(SAMPLE_DIR, "ats_data.json")}
        result = process_candidate(sources)
        assert result["is_valid"]
        assert result["output"]["full_name"] == "Priya Sharma"

    def test_missing_source_graceful(self):
        sources = {
            "ats_json": os.path.join(SAMPLE_DIR, "ats_data.json"),
            "resume_pdf": "/nonexistent/resume.pdf",
        }
        result = process_candidate(sources)
        # Should still produce output from the valid source
        assert result["output"]
        assert result["output"]["full_name"] == "Priya Sharma"
