"""
Runtime config schema — validates and parses output configuration.

The config controls ONLY the output shape. It never affects
extraction, normalization, or merging.
"""

import json
import os
from src.errors import ConfigError
from src.logger import logger

# All valid canonical paths that can be projected
VALID_CANONICAL_PATHS = {
    "candidate_id", "full_name", "emails", "phones",
    "location", "links", "headline", "years_experience",
    "skills", "experience", "education",
    "provenance", "overall_confidence",
}

VALID_MISSING_STRATEGIES = {"null", "omit", "error"}

VALID_NORMALIZATIONS = {
    "title_case", "upper_case", "lower_case", "E164", "canonical", None,
}


def load_output_config(config_path=None, config_dict=None):
    """
    Load and validate a runtime output config.

    Args:
        config_path: Path to a JSON config file.
        config_dict: Already-parsed dict (alternative to file).

    Returns:
        Validated config dict.

    Raises:
        ConfigError if the config is invalid.
    """
    if config_dict:
        config = config_dict
    elif config_path:
        if not os.path.exists(config_path):
            raise ConfigError(f"Config file not found: {config_path}")
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Invalid JSON in config: {str(e)}")
    else:
        # Load default config
        default_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "output_configs", "default.json"
        )
        if os.path.exists(default_path):
            with open(default_path, "r") as f:
                config = json.load(f)
        else:
            config = _default_config()

    # Validate
    _validate_config(config)
    logger.info("config", "", "Output config loaded and validated")
    return config


def _validate_config(config):
    """Validate the output config structure."""
    if not isinstance(config, dict):
        raise ConfigError("Config must be a JSON object")

    # Check version
    version = config.get("version")
    if version and version not in ["1.0"]:
        raise ConfigError(f"Unsupported config version: {version}")

    # Check fields
    fields = config.get("fields")
    if fields is not None:
        if not isinstance(fields, list):
            raise ConfigError("'fields' must be a list")

        output_names = set()
        for i, field in enumerate(fields):
            if not isinstance(field, dict):
                raise ConfigError(f"Field entry {i} must be a dict")

            # Support both assignment specification and backward compatibility
            path = field.get("path", field.get("output_name"))
            if not path:
                raise ConfigError(f"Field entry {i} missing 'path' or 'output_name'")
            
            canonical_path = field.get("from", field.get("canonical_path", path))
            if not canonical_path:
                raise ConfigError(f"Field entry {i} missing 'from' or 'canonical_path'")

            # Validate canonical path (check base path)
            base_path = canonical_path.split("[")[0].split(".")[0]
            if base_path not in VALID_CANONICAL_PATHS:
                raise ConfigError(
                    f"Unknown canonical path: '{canonical_path}'. "
                    f"Valid paths: {sorted(VALID_CANONICAL_PATHS)}"
                )

            # Check for duplicate output names
            if path in output_names:
                raise ConfigError(f"Duplicate path/output_name: '{path}'")
            output_names.add(path)

            # Validate normalization rule
            normalize = field.get("normalize")
            if normalize and normalize not in VALID_NORMALIZATIONS:
                raise ConfigError(
                    f"Invalid normalize rule: '{normalize}'. "
                    f"Valid: {sorted(n for n in VALID_NORMALIZATIONS if n)}"
                )

    # Check missing_value_strategy / on_missing
    strategy = config.get("on_missing", config.get("missing_value_strategy", "null"))
    if strategy not in VALID_MISSING_STRATEGIES:
        raise ConfigError(
            f"Invalid on_missing strategy: '{strategy}'. "
            f"Valid: {sorted(VALID_MISSING_STRATEGIES)}"
        )

    # Check booleans
    for key in ["include_provenance", "include_confidence"]:
        val = config.get(key)
        if val is not None and not isinstance(val, bool):
            raise ConfigError(f"'{key}' must be a boolean")


def _default_config():
    """Return a default config that emits all fields."""
    return {
        "version": "1.0",
        "fields": [
            {"path": path, "from": path}
            for path in sorted(VALID_CANONICAL_PATHS)
        ],
        "include_provenance": True,
        "include_confidence": True,
        "on_missing": "null",
    }
