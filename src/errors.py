"""
Custom exceptions for the candidate transformer pipeline.

Error taxonomy:
- SourceError      : Problems reading/accessing a source file or API
- ParseError       : Problems parsing content from a source
- NormalizationError: Problems normalizing a field value
- ConfigError      : Invalid runtime configuration
- ValidationError  : Output fails schema validation
"""


class TransformerBaseError(Exception):
    """Base exception for all transformer errors."""

    def __init__(self, message, source="", field_path="", severity="error"):
        super().__init__(message)
        self.message = message
        self.source = source
        self.field_path = field_path
        self.severity = severity

    def to_dict(self):
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "source": self.source,
            "field_path": self.field_path,
            "severity": self.severity,
        }


class SourceError(TransformerBaseError):
    """File not found, corrupted file, API timeout, etc."""
    pass


class ParseError(TransformerBaseError):
    """Invalid JSON, malformed CSV row, etc."""
    pass


class NormalizationError(TransformerBaseError):
    """Unparseable phone, invalid date, etc."""
    pass


class ConfigError(TransformerBaseError):
    """Invalid runtime config — this is a hard failure."""
    pass


class ValidationError(TransformerBaseError):
    """Output fails schema validation."""
    pass


class ErrorCollector:
    """
    Accumulates errors during pipeline execution instead of raising.

    This allows the pipeline to continue processing even when some
    sources or fields have problems, and report all issues at the end.
    """

    def __init__(self):
        self.errors = []

    def add(self, error):
        """Add an error (exception or dict) to the collection."""
        if isinstance(error, TransformerBaseError):
            self.errors.append(error.to_dict())
        elif isinstance(error, dict):
            self.errors.append(error)
        else:
            self.errors.append({
                "error_type": "UnknownError",
                "message": str(error),
                "source": "",
                "field_path": "",
                "severity": "error",
            })

    def has_errors(self):
        return len(self.errors) > 0

    def get_errors(self):
        return list(self.errors)

    def get_by_severity(self, severity):
        return [e for e in self.errors if e.get("severity") == severity]

    def clear(self):
        self.errors = []
