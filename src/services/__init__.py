"""
Services module for business logic.
Follows Single Responsibility Principle - separates business logic from CLI.
"""

from src.services.scraper_service import ScraperService

__all__ = ["ScraperService"]
