"""
Field normalizers — pure functions that normalize raw values into canonical forms.

Each normalizer takes a raw value and returns the normalized value.
If normalization fails, it returns None (never fabricates data).
"""

import re
import os
import yaml


# ──────────────────────────────────────────────
#  NAME NORMALIZER
# ──────────────────────────────────────────────

def normalize_name(raw_name):
    """
    Normalize a name string.
    - Strip whitespace
    - Handle "Last, First" format
    - Remove salutations (Mr., Mrs., Dr., etc.)
    - Title-case
    """
    if not raw_name or not isinstance(raw_name, str):
        return None

    name = raw_name.strip()
    if not name:
        return None

    # Remove salutations
    salutations = r'^(Mr\.?|Mrs\.?|Ms\.?|Dr\.?|Prof\.?|Sir|Madam)\s+'
    name = re.sub(salutations, '', name, flags=re.IGNORECASE).strip()

    # Remove suffixes
    suffixes = r'\s+(Jr\.?|Sr\.?|II|III|IV|PhD|MD|Esq\.?)$'
    name = re.sub(suffixes, '', name, flags=re.IGNORECASE).strip()

    # Handle "Last, First" format
    if ',' in name:
        parts = name.split(',', 1)
        if len(parts) == 2:
            name = f"{parts[1].strip()} {parts[0].strip()}"

    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()

    # Title case
    name = name.title()

    return name if name else None


# ──────────────────────────────────────────────
#  EMAIL NORMALIZER
# ──────────────────────────────────────────────

def normalize_email(raw_email):
    """
    Normalize an email address.
    - Lowercase
    - Strip whitespace
    - Validate RFC 5322 (basic)
    - Returns None if invalid
    """
    if not raw_email or not isinstance(raw_email, str):
        return None

    email = raw_email.strip().lower()

    # Basic email validation
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        return None

    return email


def normalize_email_list(raw_emails):
    """Normalize a list of emails, removing invalid ones and duplicates."""
    if not raw_emails or not isinstance(raw_emails, list):
        return []

    seen = set()
    result = []
    for email in raw_emails:
        normalized = normalize_email(email)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)  # Sort for determinism


# ──────────────────────────────────────────────
#  PHONE NORMALIZER
# ──────────────────────────────────────────────

def normalize_phone(raw_phone):
    """
    Normalize a phone number to E.164-like format.
    - Strips non-digit characters (except leading +)
    - Validates length (7-15 digits)
    - Returns None if invalid
    """
    if not raw_phone or not isinstance(raw_phone, str):
        return None

    phone = raw_phone.strip()

    # Try using phonenumbers library if available
    try:
        import phonenumbers
        parsed = phonenumbers.parse(phone, "US")  # Default to US
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass

    # Fallback: manual normalization
    has_plus = phone.startswith('+')
    digits = re.sub(r'\D', '', phone)

    if len(digits) < 7 or len(digits) > 15:
        return None

    if has_plus:
        return f"+{digits}"
    elif len(digits) == 10:
        return f"+1{digits}"  # Assume US
    else:
        return f"+{digits}"


def normalize_phone_list(raw_phones):
    """Normalize a list of phone numbers, removing invalid ones and duplicates."""
    if not raw_phones or not isinstance(raw_phones, list):
        return []

    seen = set()
    result = []
    for phone in raw_phones:
        normalized = normalize_phone(phone)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)


# ──────────────────────────────────────────────
#  LOCATION NORMALIZER
# ──────────────────────────────────────────────

# US state abbreviation map
US_STATES = {
    "al": "Alabama", "ak": "Alaska", "az": "Arizona", "ar": "Arkansas",
    "ca": "California", "co": "Colorado", "ct": "Connecticut", "de": "Delaware",
    "fl": "Florida", "ga": "Georgia", "hi": "Hawaii", "id": "Idaho",
    "il": "Illinois", "in": "Indiana", "ia": "Iowa", "ks": "Kansas",
    "ky": "Kentucky", "la": "Louisiana", "me": "Maine", "md": "Maryland",
    "ma": "Massachusetts", "mi": "Michigan", "mn": "Minnesota", "ms": "Mississippi",
    "mo": "Missouri", "mt": "Montana", "ne": "Nebraska", "nv": "Nevada",
    "nh": "New Hampshire", "nj": "New Jersey", "nm": "New Mexico", "ny": "New York",
    "nc": "North Carolina", "nd": "North Dakota", "oh": "Ohio", "ok": "Oklahoma",
    "or": "Oregon", "pa": "Pennsylvania", "ri": "Rhode Island", "sc": "South Carolina",
    "sd": "South Dakota", "tn": "Tennessee", "tx": "Texas", "ut": "Utah",
    "vt": "Vermont", "va": "Virginia", "wa": "Washington", "wv": "West Virginia",
    "wi": "Wisconsin", "wy": "Wyoming", "dc": "District of Columbia",
}


def normalize_location(raw_location):
    """
    Normalize a location string into {city, state, country}.
    Returns a dict with city, state, country, raw.
    """
    if not raw_location or not isinstance(raw_location, str):
        return None

    raw = raw_location.strip()
    if not raw:
        return None

    result = {"city": None, "state": None, "country": None, "raw": raw}

    # Split by comma
    parts = [p.strip() for p in raw.split(",")]

    if len(parts) >= 3:
        result["city"] = parts[0].title()
        result["state"] = parts[1].strip()
        result["country"] = parts[2].strip().title()
    elif len(parts) == 2:
        result["city"] = parts[0].title()
        second = parts[1].strip()

        # Check if second part is a US state abbreviation
        if second.lower() in US_STATES:
            result["state"] = US_STATES[second.lower()]
            result["country"] = "United States"
        elif len(second) == 2 and second.upper().isalpha():
            # Could be a state abbreviation
            if second.lower() in US_STATES:
                result["state"] = US_STATES[second.lower()]
                result["country"] = "United States"
            else:
                result["state"] = second
        else:
            result["state"] = second.title()
    elif len(parts) == 1:
        result["city"] = parts[0].title()

    return result


# ──────────────────────────────────────────────
#  SKILLS NORMALIZER
# ──────────────────────────────────────────────

def _load_skill_aliases():
    """Load skill alias map from config file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "skill_aliases.yaml"
    )
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("aliases", {})
    except Exception:
        return {}


_SKILL_ALIASES = None


def _get_skill_aliases():
    global _SKILL_ALIASES
    if _SKILL_ALIASES is None:
        _SKILL_ALIASES = _load_skill_aliases()
    return _SKILL_ALIASES


def normalize_skill(raw_skill):
    """Normalize a skill name using alias map. Returns canonical name."""
    if not raw_skill or not isinstance(raw_skill, str):
        return None

    skill = raw_skill.strip().lower()
    if not skill:
        return None

    # Check alias map
    aliases = _get_skill_aliases()
    canonical = aliases.get(skill, skill)

    return canonical


def normalize_skill_list(raw_skills):
    """Normalize a list of skills, dedup and sort."""
    if not raw_skills or not isinstance(raw_skills, list):
        return []

    seen = set()
    result = []
    for skill in raw_skills:
        normalized = normalize_skill(skill)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return sorted(result)


# ──────────────────────────────────────────────
#  DATE NORMALIZER
# ──────────────────────────────────────────────

def normalize_date(raw_date):
    """
    Normalize a date string to ISO 8601 (YYYY-MM-DD or YYYY-MM or YYYY).
    Handles: "Present", "Current", various formats.
    Returns None for "Present"/"Current" (use is_current flag instead).
    """
    if not raw_date or not isinstance(raw_date, str):
        return None

    date_str = raw_date.strip()

    # Handle "Present" / "Current"
    if date_str.lower() in ("present", "current", "now", "ongoing"):
        return None  # Caller should set is_current=True

    # Already ISO format
    if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
        return date_str

    if re.match(r'^\d{4}-\d{2}$', date_str):
        return date_str

    if re.match(r'^\d{4}$', date_str):
        return date_str

    # Try common formats
    from datetime import datetime

    formats = [
        "%m/%d/%Y", "%d/%m/%Y", "%m-%d-%Y",
        "%B %Y", "%b %Y",  # "January 2020", "Jan 2020"
        "%B %d, %Y",       # "January 15, 2020"
        "%d %B %Y",        # "15 January 2020"
        "%Y/%m/%d",
    ]

    for fmt in formats:
        try:
            parsed = datetime.strptime(date_str, fmt)
            return parsed.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Try to extract just a year
    year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
    if year_match:
        return year_match.group(0)

    return None


# ──────────────────────────────────────────────
#  EXPERIENCE NORMALIZER
# ──────────────────────────────────────────────

def _load_company_aliases():
    """Load company alias map from config file."""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "company_aliases.yaml"
    )
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("aliases", {})
    except Exception:
        return {}


_COMPANY_ALIASES = None


def _get_company_aliases():
    global _COMPANY_ALIASES
    if _COMPANY_ALIASES is None:
        _COMPANY_ALIASES = _load_company_aliases()
    return _COMPANY_ALIASES


def normalize_company(raw_company):
    """Normalize a company name using alias map."""
    if not raw_company or not isinstance(raw_company, str):
        return ""
    company = raw_company.strip()
    aliases = _get_company_aliases()
    return aliases.get(company.lower(), company)


def normalize_experience(raw_exp):
    """
    Normalize a single experience entry (dict).
    Returns a normalized dict.
    """
    if not raw_exp or not isinstance(raw_exp, dict):
        return None

    company = normalize_company(raw_exp.get("company", ""))
    title = raw_exp.get("title", "").strip().title() if raw_exp.get("title") else ""

    start_date = normalize_date(raw_exp.get("start_date"))
    end_date_raw = raw_exp.get("end_date", "")
    end_date = normalize_date(end_date_raw)

    # Determine is_current
    is_current = raw_exp.get("is_current", False)
    if end_date_raw and isinstance(end_date_raw, str):
        if end_date_raw.strip().lower() in ("present", "current", "now", "ongoing"):
            is_current = True

    return {
        "company": company,
        "title": title,
        "start_date": start_date,
        "end_date": end_date,
        "is_current": is_current,
        "description": raw_exp.get("description", "").strip(),
    }


def normalize_experience_list(raw_experiences):
    """Normalize and sort experience entries by start_date descending."""
    if not raw_experiences or not isinstance(raw_experiences, list):
        return []

    result = []
    for exp in raw_experiences:
        normalized = normalize_experience(exp)
        if normalized and (normalized["company"] or normalized["title"]):
            result.append(normalized)

    # Sort by start_date descending (None/empty last)
    result.sort(key=lambda x: x.get("start_date") or "0000", reverse=True)
    return result


# ──────────────────────────────────────────────
#  EDUCATION NORMALIZER
# ──────────────────────────────────────────────

DEGREE_MAP = {
    "bs": "Bachelor of Science",
    "b.s.": "Bachelor of Science",
    "b.s": "Bachelor of Science",
    "ba": "Bachelor of Arts",
    "b.a.": "Bachelor of Arts",
    "b.a": "Bachelor of Arts",
    "bsc": "Bachelor of Science",
    "btech": "Bachelor of Technology",
    "b.tech": "Bachelor of Technology",
    "be": "Bachelor of Engineering",
    "b.e.": "Bachelor of Engineering",
    "ms": "Master of Science",
    "m.s.": "Master of Science",
    "m.s": "Master of Science",
    "ma": "Master of Arts",
    "m.a.": "Master of Arts",
    "msc": "Master of Science",
    "mtech": "Master of Technology",
    "m.tech": "Master of Technology",
    "mba": "Master of Business Administration",
    "m.b.a.": "Master of Business Administration",
    "phd": "Doctor of Philosophy",
    "ph.d.": "Doctor of Philosophy",
    "ph.d": "Doctor of Philosophy",
    "md": "Doctor of Medicine",
    "m.d.": "Doctor of Medicine",
}


def normalize_degree(raw_degree):
    """Normalize a degree abbreviation to its full form."""
    if not raw_degree or not isinstance(raw_degree, str):
        return ""
    degree = raw_degree.strip()
    return DEGREE_MAP.get(degree.lower(), degree)


def normalize_education(raw_edu):
    """Normalize a single education entry (dict)."""
    if not raw_edu or not isinstance(raw_edu, dict):
        return None

    return {
        "institution": raw_edu.get("institution", "").strip().title() if raw_edu.get("institution") else "",
        "degree": normalize_degree(raw_edu.get("degree", "")),
        "field_of_study": raw_edu.get("field_of_study", "").strip().title() if raw_edu.get("field_of_study") else "",
        "start_date": normalize_date(raw_edu.get("start_date")),
        "end_date": normalize_date(raw_edu.get("end_date")),
    }


def normalize_education_list(raw_educations):
    """Normalize a list of education entries."""
    if not raw_educations or not isinstance(raw_educations, list):
        return []

    result = []
    for edu in raw_educations:
        normalized = normalize_education(edu)
        if normalized and (normalized["institution"] or normalized["degree"]):
            result.append(normalized)

    # Sort by end_date descending
    result.sort(key=lambda x: x.get("end_date") or "0000", reverse=True)
    return result


# ──────────────────────────────────────────────
#  LINK NORMALIZER
# ──────────────────────────────────────────────

def normalize_links(raw_links):
    """Normalize a dict of links — validate URLs, classify types."""
    if not raw_links or not isinstance(raw_links, dict):
        return {}

    url_pattern = re.compile(r'^https?://[^\s<>\"\']+$')
    result = {}

    for key, value in raw_links.items():
        if not value or not isinstance(value, str):
            continue
        url = value.strip()
        if url_pattern.match(url):
            result[key.lower().strip()] = url

    return result
