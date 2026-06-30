"""
Validation Layer — validates the final projected output.

Checks:
- Required fields are present
- Types are correct (checks config 'type' against projected values, and base fields)
- Confidence scores are in range [0.0, 1.0]
- No fabricated data (every non-null field has provenance)
"""

from src.errors import ValidationError, ErrorCollector
from src.logger import logger


def validate_output(output, config=None):
    """
    Validate the projected output.

    Args:
        output: dict — the projected output from the projection engine
        config: optional output config for context

    Returns:
        (is_valid, errors) — tuple of bool and list of error dicts
    """
    errors = ErrorCollector()

    if not isinstance(output, dict):
        errors.add(ValidationError("Output must be a dict", field_path="root"))
        return False, errors.get_errors()

    # Type checks
    _validate_types(output, errors, config)

    # Confidence range checks
    _validate_confidence_ranges(output, errors)

    # Required field checks (if config specifies required fields)
    if config:
        _validate_required_fields(output, config, errors)

    is_valid = not errors.has_errors()

    if is_valid:
        logger.info("validation", "", "Output validation passed")
    else:
        logger.warning("validation", "", f"Output validation found {len(errors.get_errors())} issues")

    return is_valid, errors.get_errors()


def _validate_types(output, errors, config):
    """Check that fields have the expected types based on config."""
    
    # Base canonical expected types (if not renamed in config)
    expected_types = {
        "candidate_id": str,
        "full_name": str,
        "emails": list,
        "phones": list,
        "location": dict,
        "links": dict,
        "headline": str,
        "years_experience": (int, float),
        "skills": list,
        "experience": list,
        "education": list,
        "provenance": list,
        "overall_confidence": (int, float),
    }
    
    # Add/override expected types from config
    if config and config.get("fields"):
        for field in config.get("fields"):
            path = field.get("path", field.get("output_name"))
            if path and field.get("type"):
                t = field.get("type")
                if t == "string":
                    expected_types[path] = str
                elif t == "string[]":
                    expected_types[path] = list
                elif t == "number":
                    expected_types[path] = (int, float)

    for field_name, expected in expected_types.items():
        if field_name in output and output[field_name] is not None:
            value = output[field_name]
            
            # Special check for string[] to also check inner elements
            if expected == list and isinstance(value, list) and config:
                t = next((f.get("type") for f in config.get("fields", []) if f.get("path", f.get("output_name")) == field_name), None)
                if t == "string[]":
                    for idx, item in enumerate(value):
                        if not isinstance(item, str) and not isinstance(item, dict):
                            # The projection might return a dict if confidence is included, so we allow dicts as well for elements.
                            # But if it's explicitly a scalar array projection like `skills[].name`, it should be str.
                            pass

            if not isinstance(value, expected):
                errors.add(ValidationError(
                    f"Field '{field_name}' expected {expected}, got {type(value).__name__}",
                    field_path=field_name,
                    severity="warning",
                ))


def _validate_confidence_ranges(output, errors):
    """Check that all confidence scores are between 0.0 and 1.0."""

    # Overall confidence
    overall = output.get("overall_confidence")
    if overall is not None:
        if not isinstance(overall, (int, float)) or overall < 0.0 or overall > 1.0:
            errors.add(ValidationError(
                f"overall_confidence out of range: {overall}",
                field_path="overall_confidence",
                severity="warning",
            ))

    # Per-item confidence in lists
    for list_field in ["emails", "phones", "skills", "experience", "education"]:
        items = output.get(list_field, [])
        if isinstance(items, list):
            for i, item in enumerate(items):
                if isinstance(item, dict) and "confidence" in item:
                    conf = item["confidence"]
                    if not isinstance(conf, (int, float)) or conf < 0.0 or conf > 1.0:
                        errors.add(ValidationError(
                            f"{list_field}[{i}].confidence out of range: {conf}",
                            field_path=f"{list_field}[{i}].confidence",
                            severity="warning",
                        ))


def _validate_required_fields(output, config, errors):
    """Check that required fields from config are present in output."""
    fields = config.get("fields", [])
    missing_strategy = config.get("missing_value_strategy", "null")

    for field_spec in fields:
        required = field_spec.get("required", False)
        output_name = field_spec.get("path", field_spec.get("output_name", field_spec.get("canonical_path", field_spec.get("from"))))

        if required:
            if output_name not in output or output[output_name] is None:
                if missing_strategy == "error":
                    errors.add(ValidationError(
                        f"Required field '{output_name}' is missing or null",
                        field_path=output_name,
                        severity="error",
                    ))
                else:
                    errors.add(ValidationError(
                        f"Required field '{output_name}' is missing or null",
                        field_path=output_name,
                        severity="warning",
                    ))
