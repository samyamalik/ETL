"""
Base adapter — abstract contract that every source adapter must implement.

To add a new source:
1. Subclass BaseAdapter
2. Implement extract()
3. Register with the AdapterRegistry

That's it. Zero changes to existing code.
"""

from abc import ABC, abstractmethod
from src.schema.source_record import SourceRecord


class BaseAdapter(ABC):
    """Abstract base class for all source adapters."""

    def __init__(self):
        self.source_name = ""            # e.g. "ats_json"
        self.supported_extensions = []   # e.g. [".json"]

    def can_handle(self, file_path):
        """Check if this adapter can handle the given file."""
        if not file_path:
            return False
        lower = file_path.lower()
        return any(lower.endswith(ext) for ext in self.supported_extensions)

    @abstractmethod
    def extract(self, input_data):
        """
        Extract candidate data from the input.

        Args:
            input_data: File path (str) or dict for API-based sources.

        Returns:
            SourceRecord with extracted fields, or SourceRecord with errors.

        Must NEVER raise an exception. Catch all errors internally.
        """
        pass

    def _empty_record_with_error(self, error_message):
        """Helper: return an empty SourceRecord with an error logged."""
        record = SourceRecord(source_name=self.source_name)
        record.errors.append(error_message)
        return record
