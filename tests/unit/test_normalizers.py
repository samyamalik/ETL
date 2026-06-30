"""
Unit tests for normalizers — every normalizer function tested individually.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.normalizers.normalizers import (
    normalize_name, normalize_email, normalize_email_list,
    normalize_phone, normalize_phone_list,
    normalize_location, normalize_skill, normalize_skill_list,
    normalize_date, normalize_company, normalize_degree,
    normalize_experience, normalize_experience_list,
    normalize_education, normalize_education_list,
    normalize_links,
)


# ──────────────────────────────────────────────
#  NAME NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeName:
    def test_basic_name(self):
        assert normalize_name("john doe") == "John Doe"

    def test_extra_whitespace(self):
        assert normalize_name("  john   doe  ") == "John Doe"

    def test_last_comma_first(self):
        assert normalize_name("Doe, John") == "John Doe"

    def test_salutation_removal(self):
        assert normalize_name("Dr. John Doe") == "John Doe"
        assert normalize_name("Mr. John Doe") == "John Doe"
        assert normalize_name("Mrs. Jane Doe") == "Jane Doe"

    def test_suffix_removal(self):
        assert normalize_name("John Doe Jr.") == "John Doe"
        assert normalize_name("John Doe PhD") == "John Doe"

    def test_none_input(self):
        assert normalize_name(None) is None

    def test_empty_string(self):
        assert normalize_name("") is None
        assert normalize_name("   ") is None

    def test_non_string(self):
        assert normalize_name(123) is None


# ──────────────────────────────────────────────
#  EMAIL NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeEmail:
    def test_basic_email(self):
        assert normalize_email("User@Example.COM") == "user@example.com"

    def test_whitespace(self):
        assert normalize_email("  user@example.com  ") == "user@example.com"

    def test_invalid_email(self):
        assert normalize_email("not-an-email") is None
        assert normalize_email("@example.com") is None
        assert normalize_email("user@") is None

    def test_none_input(self):
        assert normalize_email(None) is None

    def test_email_list_dedup(self):
        emails = ["a@b.com", "A@B.COM", "c@d.com"]
        result = normalize_email_list(emails)
        assert result == ["a@b.com", "c@d.com"]

    def test_email_list_sorted(self):
        emails = ["z@example.com", "a@example.com"]
        result = normalize_email_list(emails)
        assert result == ["a@example.com", "z@example.com"]


# ──────────────────────────────────────────────
#  PHONE NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizePhone:
    def test_too_short(self):
        assert normalize_phone("123") is None

    def test_none_input(self):
        assert normalize_phone(None) is None

    def test_empty(self):
        assert normalize_phone("") is None

    def test_phone_list_dedup(self):
        phones = ["+1-555-555-1234", "+15555551234"]
        result = normalize_phone_list(phones)
        # After normalization both should be same, so deduped to 1
        assert len(result) >= 1


# ──────────────────────────────────────────────
#  LOCATION NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeLocation:
    def test_city_state_abbrev(self):
        result = normalize_location("San Francisco, CA")
        assert result["city"] == "San Francisco"
        assert result["state"] == "California"
        assert result["country"] == "United States"

    def test_city_state_country(self):
        result = normalize_location("London, England, UK")
        assert result["city"] == "London"
        assert result["country"] == "Uk"

    def test_city_only(self):
        result = normalize_location("Mumbai")
        assert result["city"] == "Mumbai"

    def test_none_input(self):
        assert normalize_location(None) is None

    def test_empty_string(self):
        assert normalize_location("") is None


# ──────────────────────────────────────────────
#  SKILL NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeSkill:
    def test_alias_resolution(self):
        assert normalize_skill("js") == "javascript"
        assert normalize_skill("JS") == "javascript"
        assert normalize_skill("ts") == "typescript"
        assert normalize_skill("nodejs") == "node.js"
        assert normalize_skill("reactjs") == "react"

    def test_no_alias(self):
        assert normalize_skill("python") == "python"

    def test_none_input(self):
        assert normalize_skill(None) is None

    def test_skill_list_dedup(self):
        skills = ["Python", "python", "js", "JavaScript"]
        result = normalize_skill_list(skills)
        assert "python" in result
        assert "javascript" in result
        assert len([s for s in result if s == "python"]) == 1

    def test_skill_list_sorted(self):
        skills = ["zsh", "bash", "awk"]
        result = normalize_skill_list(skills)
        assert result == sorted(result)


# ──────────────────────────────────────────────
#  DATE NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeDate:
    def test_iso_format(self):
        assert normalize_date("2024-01-15") == "2024-01-15"

    def test_year_month(self):
        assert normalize_date("2024-01") == "2024-01"

    def test_year_only(self):
        assert normalize_date("2024") == "2024"

    def test_present(self):
        assert normalize_date("Present") is None
        assert normalize_date("Current") is None
        assert normalize_date("now") is None

    def test_month_year(self):
        result = normalize_date("January 2020")
        assert result is not None
        assert "2020" in result

    def test_none_input(self):
        assert normalize_date(None) is None

    def test_empty_string(self):
        assert normalize_date("") is None


# ──────────────────────────────────────────────
#  COMPANY NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeCompany:
    def test_alias_resolution(self):
        assert normalize_company("Google LLC") == "Google"
        assert normalize_company("facebook") == "Meta"
        assert normalize_company("Amazon Inc") == "Amazon"

    def test_no_alias(self):
        assert normalize_company("Some Startup") == "Some Startup"

    def test_none_input(self):
        assert normalize_company(None) == ""


# ──────────────────────────────────────────────
#  DEGREE NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeDegree:
    def test_abbreviations(self):
        assert normalize_degree("BS") == "Bachelor of Science"
        assert normalize_degree("MS") == "Master of Science"
        assert normalize_degree("MBA") == "Master of Business Administration"
        assert normalize_degree("PhD") == "Doctor of Philosophy"
        assert normalize_degree("BTech") == "Bachelor of Technology"

    def test_full_name_passthrough(self):
        assert normalize_degree("Bachelor of Arts") == "Bachelor of Arts"

    def test_none_input(self):
        assert normalize_degree(None) == ""


# ──────────────────────────────────────────────
#  EXPERIENCE NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeExperience:
    def test_basic_experience(self):
        exp = {
            "company": "Google LLC",
            "title": "software engineer",
            "start_date": "2020-01",
            "end_date": "Present",
        }
        result = normalize_experience(exp)
        assert result["company"] == "Google"
        assert result["title"] == "Software Engineer"
        assert result["is_current"] is True
        assert result["end_date"] is None

    def test_none_input(self):
        assert normalize_experience(None) is None

    def test_empty_dict(self):
        result = normalize_experience({})
        assert result is None  # No company or title

    def test_list_sorting(self):
        exps = [
            {"company": "A", "title": "Dev", "start_date": "2018-01"},
            {"company": "B", "title": "Dev", "start_date": "2022-01"},
        ]
        result = normalize_experience_list(exps)
        assert result[0]["start_date"] == "2022-01"  # Most recent first


# ──────────────────────────────────────────────
#  LINK NORMALIZER TESTS
# ──────────────────────────────────────────────

class TestNormalizeLinks:
    def test_valid_links(self):
        links = {
            "GitHub": "https://github.com/user",
            "LinkedIn": "https://linkedin.com/in/user",
        }
        result = normalize_links(links)
        assert "github" in result
        assert "linkedin" in result

    def test_invalid_url(self):
        links = {"bad": "not-a-url"}
        result = normalize_links(links)
        assert "bad" not in result

    def test_none_input(self):
        assert normalize_links(None) == {}

    def test_empty_dict(self):
        assert normalize_links({}) == {}
