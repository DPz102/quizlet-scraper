"""
Exporter Factory - Creates appropriate exporter based on format.
Following Factory Pattern and Dependency Inversion Principle.
"""

from typing import Dict, Type, Optional
from enum import Enum
import logging

from src.core.interfaces import BaseExporter
from src.export.json_exporter import JSONExporter
from src.export.csv_exporter import CSVExporter, TSVExporter
from src.export.anki_exporter import AnkiExporter

logger = logging.getLogger(__name__)


class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    CSV = "csv"
    TSV = "tsv"
    ANKI = "anki"


class ExporterFactory:
    """
    Factory for creating exporters.
    Dependency Inversion: High-level modules don't depend on concrete exporters.
    """
    
    # Registry of exporters
    _registry: Dict[ExportFormat, Type[BaseExporter]] = {
        ExportFormat.JSON: JSONExporter,
        ExportFormat.CSV: CSVExporter,
        ExportFormat.TSV: TSVExporter,
        ExportFormat.ANKI: AnkiExporter,
    }
    
    @classmethod
    def create(
        cls,
        format: ExportFormat,
        **kwargs
    ) -> BaseExporter:
        """
        Create an exporter for the specified format.
        
        Args:
            format: Export format to use.
            **kwargs: Additional arguments for the exporter.
            
        Returns:
            BaseExporter instance.
            
        Raises:
            ValueError: If format is not supported.
        """
        if format not in cls._registry:
            raise ValueError(f"Unsupported export format: {format}")
        
        exporter_class = cls._registry[format]
        return exporter_class(**kwargs)
    
    @classmethod
    def create_from_string(cls, format_str: str, **kwargs) -> BaseExporter:
        """
        Create an exporter from format string.
        
        Args:
            format_str: Format string (e.g., "json", "csv").
            **kwargs: Additional arguments for the exporter.
            
        Returns:
            BaseExporter instance.
        """
        try:
            format = ExportFormat(format_str.lower())
            return cls.create(format, **kwargs)
        except ValueError:
            raise ValueError(f"Unsupported export format: {format_str}")
    
    @classmethod
    def register(cls, format: ExportFormat, exporter_class: Type[BaseExporter]) -> None:
        """
        Register a new exporter.
        Open/Closed: Can add new exporters without modifying existing code.
        
        Args:
            format: Export format.
            exporter_class: Exporter class to register.
        """
        cls._registry[format] = exporter_class
        logger.info(f"Registered exporter for format: {format.value}")
    
    @classmethod
    def get_supported_formats(cls) -> list:
        """Get list of supported format strings."""
        return [f.value for f in cls._registry.keys()]
