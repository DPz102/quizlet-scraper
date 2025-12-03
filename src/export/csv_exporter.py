"""
CSV Exporter implementation.
Following Open/Closed Principle - extends BaseExporter without modification.
"""

import csv
import io
import logging
from typing import Optional

from src.core.interfaces import BaseExporter, FlashCardSet

logger = logging.getLogger(__name__)


class CSVExporter(BaseExporter):
    """
    Exports flashcard sets to CSV format.
    Open/Closed: Extends BaseExporter, closed for modification.
    """
    
    def __init__(
        self,
        delimiter: str = ",",
        include_header: bool = True,
        include_images: bool = False
    ):
        """
        Initialize CSV exporter.
        
        Args:
            delimiter: Field delimiter (comma, tab, etc.).
            include_header: Whether to include header row.
            include_images: Whether to include image URLs.
        """
        self._delimiter = delimiter
        self._include_header = include_header
        self._include_images = include_images
    
    @property
    def file_extension(self) -> str:
        return ".csv"
    
    def _serialize(self, flashcard_set: FlashCardSet) -> str:
        """Serialize flashcard set to CSV string."""
        output = io.StringIO()
        
        if self._include_images:
            fieldnames = ["term", "definition", "image_url"]
        else:
            fieldnames = ["term", "definition"]
        
        writer = csv.DictWriter(
            output,
            fieldnames=fieldnames,
            delimiter=self._delimiter,
            quoting=csv.QUOTE_ALL
        )
        
        if self._include_header:
            writer.writeheader()
        
        for card in flashcard_set.cards:
            row = {
                "term": card.term,
                "definition": card.definition
            }
            if self._include_images:
                row["image_url"] = card.image_url or ""
            
            writer.writerow(row)
        
        return output.getvalue()


class TSVExporter(CSVExporter):
    """
    Exports flashcard sets to TSV (Tab-Separated Values) format.
    Liskov Substitution: Can be used anywhere CSVExporter is expected.
    """
    
    def __init__(self, include_header: bool = True, include_images: bool = False):
        super().__init__(
            delimiter="\t",
            include_header=include_header,
            include_images=include_images
        )
    
    @property
    def file_extension(self) -> str:
        return ".tsv"
