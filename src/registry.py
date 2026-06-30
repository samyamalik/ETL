"""
Adapter registry — manages and dispatches source adapters.

New sources are added by calling registry.register(adapter).
The pipeline uses registry.get_adapter(source_type) to find the right adapter.
"""

from src.logger import logger


class AdapterRegistry:
    """Central registry for all source adapters."""

    def __init__(self):
        self._adapters = {}

    def register(self, adapter):
        """Register an adapter by its source_name."""
        self._adapters[adapter.source_name] = adapter
        logger.info("registry", adapter.source_name, "Adapter registered")

    def get_adapter(self, source_type):
        """Get an adapter by source type name. Returns None if not found."""
        adapter = self._adapters.get(source_type)
        if not adapter:
            logger.warning("registry", source_type, "No adapter found for source type")
        return adapter

    def get_adapter_for_file(self, file_path):
        """Find an adapter that can handle the given file path."""
        for adapter in self._adapters.values():
            if adapter.can_handle(file_path):
                return adapter
        logger.warning("registry", "", f"No adapter found for file: {file_path}")
        return None

    def list_adapters(self):
        """List all registered adapter names."""
        return list(self._adapters.keys())
