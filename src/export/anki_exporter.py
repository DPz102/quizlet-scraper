"""
Anki-compatible exporter implementation.
Following Open/Closed Principle - extends BaseExporter without modification.
"""

import logging
from typing import Optional

from src.core.interfaces import BaseExporter, FlashCardSet

logger = logging.getLogger(__name__)


class AnkiExporter(BaseExporter):
    """
    Exports flashcard sets to Anki-compatible TXT format.
    Open/Closed: Extends BaseExporter, closed for modification.
    
    Output format: term;definition (semicolon-separated)
    This can be directly imported into Anki.
    """
    
    def __init__(self, delimiter: str = ";", include_tags: bool = False):
        """
        Initialize Anki exporter.
        
        Args:
            delimiter: Field delimiter (Anki default is semicolon).
            include_tags: Whether to add set title as tag.
        """
        self._delimiter = delimiter
        self._include_tags = include_tags
    
    @property
    def file_extension(self) -> str:
        return ".txt"
    
    def _serialize(self, flashcard_set: FlashCardSet) -> str:
        """Serialize flashcard set to Anki-compatible format."""
        lines = []
        
        # Add header comment
        lines.append(f"# {flashcard_set.title}")
        lines.append(f"# Exported from Quizlet - {len(flashcard_set.cards)} cards")
        lines.append("")
        
        for card in flashcard_set.cards:
            # Escape delimiter in content
            term = card.term.replace(self._delimiter, ",")
            definition = card.definition.replace(self._delimiter, ",")
            
            # Remove newlines (Anki doesn't handle them well in plain import)
            term = term.replace("\n", " ").replace("\r", "")
            definition = definition.replace("\n", " ").replace("\r", "")
            
            if self._include_tags:
                # Add set title as tag (replace spaces with underscores)
                tag = flashcard_set.title.replace(" ", "_")
                line = f"{term}{self._delimiter}{definition}{self._delimiter}{tag}"
            else:
                line = f"{term}{self._delimiter}{definition}"
            
            lines.append(line)
        
        return "\n".join(lines)
