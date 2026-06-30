"""Unit tests for projection engine and config validation."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from src.schema.source_record import SourceRecord
from src.merger.merge_engine import merge_records
from src.scoring.confidence import score_profile
from src.provenance.tracker import track_provenance
from src.projection.engine import project
from src.projection.config_schema import load_output_config
from src.validation.validator import validate_output
from src.errors import ConfigError

def _build_profile():
    records = [SourceRecord(source_name="ats_json", extraction_method="structured",
        full_name="John Doe", emails=["john@example.com"], skills=["Python","React"],
        headline="Senior Engineer", years_experience=5.0)]
    profile = merge_records(records)
    profile = score_profile(profile, records)
    profile = track_provenance(profile, records)
    return profile

class TestProjection:
    def test_default_config(self):
        profile = _build_profile()
        config = load_output_config()
        output = project(profile, config)
        assert "full_name" in output or "candidate_id" in output

    def test_field_selection(self):
        profile = _build_profile()
        config = {"version": "1.0", "fields": [
            {"canonical_path": "full_name", "output_name": "name"},
        ], "include_provenance": False, "include_confidence": False, "missing_value_strategy": "null"}
        config = load_output_config(config_dict=config)
        output = project(profile, config)
        assert "name" in output
        assert "emails" not in output

    def test_field_renaming(self):
        profile = _build_profile()
        config = {"version": "1.0", "fields": [
            {"canonical_path": "full_name", "output_name": "candidateName"},
            {"canonical_path": "skills", "output_name": "technicalSkills"},
        ], "include_provenance": False, "include_confidence": True, "missing_value_strategy": "null"}
        config = load_output_config(config_dict=config)
        output = project(profile, config)
        assert "candidateName" in output
        assert "technicalSkills" in output

    def test_provenance_stripped(self):
        profile = _build_profile()
        config = {"version": "1.0", "fields": [
            {"canonical_path": "full_name", "output_name": "full_name"},
            {"canonical_path": "emails", "output_name": "emails"},
        ], "include_provenance": False, "include_confidence": False, "missing_value_strategy": "null"}
        config = load_output_config(config_dict=config)
        output = project(profile, config)
        # source field should be stripped from nested items
        if output.get("emails") and isinstance(output["emails"], list):
            for item in output["emails"]:
                if isinstance(item, dict):
                    assert "source" not in item

    def test_missing_value_null(self):
        profile = _build_profile()
        config = {"version": "1.0", "fields": [
            {"canonical_path": "location", "output_name": "location"},
        ], "include_provenance": False, "include_confidence": False, "missing_value_strategy": "null"}
        config = load_output_config(config_dict=config)
        output = project(profile, config)
        assert "location" in output  # Should be present (as None)

    def test_missing_value_omit(self):
        profile = _build_profile()
        config = {"version": "1.0", "fields": [
            {"canonical_path": "location", "output_name": "location"},
        ], "include_provenance": False, "include_confidence": False, "missing_value_strategy": "omit"}
        config = load_output_config(config_dict=config)
        output = project(profile, config)
        assert "location" not in output  # Should be omitted

class TestConfigValidation:
    def test_invalid_canonical_path(self):
        config = {"version": "1.0", "fields": [
            {"canonical_path": "nonexistent_field", "output_name": "bad"},
        ]}
        with pytest.raises(ConfigError):
            load_output_config(config_dict=config)

    def test_duplicate_output_names(self):
        config = {"version": "1.0", "fields": [
            {"canonical_path": "full_name", "output_name": "name"},
            {"canonical_path": "headline", "output_name": "name"},
        ]}
        with pytest.raises(ConfigError):
            load_output_config(config_dict=config)

    def test_invalid_missing_strategy(self):
        config = {"version": "1.0", "missing_value_strategy": "invalid"}
        with pytest.raises(ConfigError):
            load_output_config(config_dict=config)

    def test_invalid_normalize_rule(self):
        config = {"version": "1.0", "fields": [
            {"canonical_path": "full_name", "output_name": "name", "normalize": "invalid_rule"},
        ]}
        with pytest.raises(ConfigError):
            load_output_config(config_dict=config)

class TestValidator:
    def test_valid_output(self):
        profile = _build_profile()
        config = load_output_config()
        output = project(profile, config)
        is_valid, errors = validate_output(output, config)
        assert is_valid

    def test_invalid_output_type(self):
        is_valid, errors = validate_output("not a dict")
        assert not is_valid
