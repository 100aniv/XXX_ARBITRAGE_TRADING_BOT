"""Backward-compatibility module for legacy imports."""

from .paper_execution_adapter import PaperExecutionAdapter as MockAdapter

__all__ = ["MockAdapter"]
