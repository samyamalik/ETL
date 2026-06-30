"""
Projection Engine — transforms a CanonicalProfile into the runtime-configured output.

This is a READ-ONLY view. It never mutates the canonical profile.

Operations applied in order:
1. Field selection
2. Field renaming
3. Path mapping
4. Field normalization (output-specific)
5. Provenance toggle
6. Confidence toggle
7. Missing value strategy
"""

from dataclasses import asdict
from src.errors import ValidationError
from src.logger import logger
import re


def project(profile, config):
    """
    Project a CanonicalProfile into the configured output shape.

    Args:
        profile: CanonicalProfile (never modified)
        config: Validated output config dict

    Returns:
        dict — the projected output
    """
    # Convert profile to a flat dict for easy field access
    profile_dict = _profile_to_dict(profile)

    fields = config.get("fields")
    include_provenance = config.get("include_provenance", True)
    include_confidence = config.get("include_confidence", True)
    missing_strategy = config.get("on_missing", config.get("missing_value_strategy", "null"))

    output = {}

    if not fields:
        # No field config — emit everything
        output = profile_dict
    else:
        for field_spec in fields:
            # Support both assignment spec and backward compatibility
            path = field_spec.get("path", field_spec.get("output_name"))
            canonical_path = field_spec.get("from", field_spec.get("canonical_path", path))
            field_type = field_spec.get("type")          # e.g. "string", "string[]", "number"
            normalize_rule = field_spec.get("normalize")
            required = field_spec.get("required", False)

            # Extract value from profile dict
            value = _resolve_path(profile_dict, canonical_path)

            # Type-aware coercion:
            # If type="string" but value is a dict (e.g. emails[0] → {address, source, …})
            # auto-extract the primary scalar so the spec path emails[0] works without .address
            if value is not None and field_type == "string":
                value = _coerce_to_string(value)
            elif value is not None and field_type == "string[]" and isinstance(value, list):
                value = [_coerce_to_string(v) if isinstance(v, dict) else v for v in value]
            elif value is not None and field_type == "number":
                value = _coerce_to_number(value)

            # Apply output normalization (does NOT affect canonical profile)
            if value is not None and normalize_rule:
                value = _apply_normalization(value, normalize_rule)

            # Handle missing values
            if value is None or (isinstance(value, list) and len(value) == 0):
                if missing_strategy == "omit":
                    continue
                elif missing_strategy == "error":
                    if required:
                        raise ValidationError(
                            f"Required field '{canonical_path}' is missing",
                            field_path=canonical_path,
                        )
                # "null" strategy: keep None
                output[path] = None
            else:
                output[path] = value

    # ── Post-projection: inject or strip confidence & provenance ──
    #
    # When a custom `fields` list is provided, only those fields are projected.
    # If the user also sets include_confidence=true or include_provenance=true,
    # we must explicitly inject those values — they are NOT in the fields list.
    # Conversely, when include_*=false, we strip them from wherever they ended up.

    if fields:
        # Custom fields mode: inject if requested
        if include_confidence:
            output["overall_confidence"] = profile_dict.get("overall_confidence")
        if include_provenance:
            output["provenance"] = profile_dict.get("provenance", [])

    # Always strip if flags are false (covers both full emit mode and custom fields mode
    # where nested objects like emails might have been explicitly requested and mapped)
    if not include_provenance:
        output.pop("provenance", None)
        _strip_nested_field(output, "source")
    if not include_confidence:
        output.pop("overall_confidence", None)
        _strip_nested_field(output, "confidence")

    logger.info("projection", "", f"Projected {len(output)} fields")
    return output


def _profile_to_dict(profile):
    """Convert a CanonicalProfile dataclass to a plain dict."""
    try:
        return asdict(profile)
    except Exception:
        # Fallback: manual conversion
        result = {}
        for attr in [
            "candidate_id", "full_name", "emails", "phones",
            "location", "links", "headline", "years_experience",
            "skills", "experience", "education",
            "provenance", "overall_confidence",
        ]:
            val = getattr(profile, attr, None)
            if hasattr(val, '__dataclass_fields__'):
                result[attr] = asdict(val)
            elif isinstance(val, list):
                result[attr] = [
                    asdict(item) if hasattr(item, '__dataclass_fields__') else item
                    for item in val
                ]
            else:
                result[attr] = val
        return result


def _resolve_path(data, path):
    """
    Resolve a dotted/bracketed path in a dict.

    Examples:
        "full_name" -> data["full_name"]
        "experience[0].title" -> data["experience"][0]["title"]
        "skills[].name" -> [skill["name"] for skill in data["skills"]]
        "skills[*].name" -> (same as above)
    """
    if not path:
        return None

    # Simple top-level key
    if path in data:
        return data[path]

    # Handle wildcard arrays: "skills[].name" or "skills[*].name"
    if "[]" in path or "[*]" in path:
        splitter = "[]" if "[]" in path else "[*]"
        base, rest = path.split(splitter, 1)
        rest = rest.lstrip(".")
        items = data.get(base, [])
        if isinstance(items, list) and rest:
            return [_resolve_path(item, rest) if isinstance(item, dict) else None for item in items]
        return items

    # Handle indexed: "experience[0].title"
    parts = path.replace("]", "").replace("[", ".").split(".")
    current = data
    for part in parts:
        if current is None:
            return None
        if part.isdigit():
            idx = int(part)
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _apply_normalization(value, rule):
    """Apply an output normalization rule to a value."""
    if isinstance(value, list):
        return [_apply_normalization(v, rule) for v in value]

    if not isinstance(value, str):
        return value

    if rule == "title_case":
        return value.title()
    elif rule == "upper_case":
        return value.upper()
    elif rule == "lower_case":
        return value.lower()
    elif rule == "E164":
        # Ensure string is formatted close to E164 if possible
        # This is a naive projection-time formatter, 
        # the real normalization happened in canonical layer.
        cleaned = re.sub(r'[^0-9+]', '', value)
        if not cleaned.startswith('+'):
            cleaned = '+' + cleaned
        return cleaned
    elif rule == "canonical":
        # Simple canonical identifier format for projection
        return value.strip().lower().replace(" ", "_")

    return value


def _strip_nested_field(data, field_name):
    """Recursively strip a field from nested dicts and lists."""
    if isinstance(data, dict):
        data.pop(field_name, None)
        for value in data.values():
            _strip_nested_field(value, field_name)
    elif isinstance(data, list):
        for item in data:
            _strip_nested_field(item, field_name)


def _coerce_to_string(value):
    """
    Coerce a dict to a primary string if a scalar string is expected.
    This resolves paths like 'emails[0]' which return a dict to extract 'address'.
    """
    if isinstance(value, dict):
        # Known primary scalar fields in canonical models
        for key in ["address", "number", "name", "city", "github", "linkedin"]:
            if key in value and isinstance(value[key], str):
                return value[key]
        # Fallback: return the first string value found
        for v in value.values():
            if isinstance(v, str):
                return v
        return str(value)
    return str(value) if value is not None else None


def _coerce_to_number(value):
    """
    Coerce a dict to a number if a number is expected.
    """
    if isinstance(value, dict):
        for v in value.values():
            if isinstance(v, (int, float)):
                return v
        return 0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0
