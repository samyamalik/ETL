"""
Structured logging for the candidate transformer pipeline.

Every log entry includes: timestamp, candidate_id, stage, source, message.
Uses Python's built-in logging with JSON-like structured output.
"""

import logging
import sys
from datetime import datetime, timezone


class PipelineLogger:
    """Simple structured logger for pipeline stages."""

    def __init__(self, name="candidate_transformer"):
        self.logger = logging.getLogger(name)
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-7s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.DEBUG)

        self.correlation_id = ""
        self.candidate_id = ""

    def set_correlation_id(self, correlation_id):
        self.correlation_id = correlation_id

    def set_candidate_id(self, candidate_id):
        self.candidate_id = candidate_id

    def _format_msg(self, stage, source, message):
        """Build a structured log message."""
        parts = []
        if self.correlation_id:
            parts.append(f"run={self.correlation_id}")
        if self.candidate_id:
            parts.append(f"candidate={self.candidate_id}")
        if stage:
            parts.append(f"stage={stage}")
        if source:
            parts.append(f"source={source}")
        parts.append(message)
        return " | ".join(parts)

    def debug(self, stage, source, message):
        self.logger.debug(self._format_msg(stage, source, message))

    def info(self, stage, source, message):
        self.logger.info(self._format_msg(stage, source, message))

    def warning(self, stage, source, message):
        self.logger.warning(self._format_msg(stage, source, message))

    def error(self, stage, source, message):
        self.logger.error(self._format_msg(stage, source, message))


# Global logger instance
logger = PipelineLogger()
