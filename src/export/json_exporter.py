"""
JSON Exporter implementation.
Following Open/Closed Principle - extends BaseExporter without modification.
"""

import json
import logging
from typing import Optional

from src.core.interfaces import BaseExporter, FlashCardSet

logger = logging.getLogger(__name__)


class JSONExporter(BaseExporter):
    """
    Exports flashcard sets to JSON format.
    Open/Closed: Extends BaseExporter, closed for modification.
    """
    
    def __init__(self, indent: int = 2, ensure_ascii: bool = False):
        """
        Initialize JSON exporter.
        
        Args:
            indent: JSON indentation level.
            ensure_ascii: Whether to escape non-ASCII characters.
        """
        self._indent = indent
        self._ensure_ascii = ensure_ascii
    
    @property
    def file_extension(self) -> str:
        return ".json"
    
    def _serialize(self, flashcard_set: FlashCardSet) -> str:
        """Serialize flashcard set to JSON string."""
        data = flashcard_set.to_dict()
        return json.dumps(
            data,
            indent=self._indent,
            ensure_ascii=self._ensure_ascii
        )
