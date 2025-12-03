"""
Core interfaces/protocols following SOLID principles.

- ISP: Each interface has a single, focused responsibility
- DIP: High-level modules depend on abstractions, not concretions
"""

from abc import ABC, abstractmethod
from typing import Protocol, List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# Data Models (Value Objects)
# ============================================================================

@dataclass(frozen=True)
class FlashCard:
    """Immutable flashcard data model."""
    term: str
    definition: str
    term_id: Optional[str] = None
    image_url: Optional[str] = None
    

@dataclass
class FlashCardSet:
    """Flashcard set with metadata."""
    set_id: str
    title: str
    url: str
    cards: List[FlashCard] = field(default_factory=lambda: [])
    description: Optional[str] = None
    created_by: Optional[str] = None
    term_count: int = 0
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for export."""
        return {
            "metadata": {
                "set_id": self.set_id,
                "title": self.title,
                "url": self.url,
                "description": self.description,
                "created_by": self.created_by,
                "term_count": len(self.cards),
                "exported_at": datetime.now().isoformat()
            },
            "cards": [
                {
                    "term": card.term,
                    "definition": card.definition,
                    "term_id": card.term_id,
                    "image_url": card.image_url
                }
                for card in self.cards
            ]
        }


@dataclass
class UserLibrary:
    """User's library containing sets, folders, classes."""
    sets: List[FlashCardSet] = field(default_factory=lambda: [])
    folder_urls: List[str] = field(default_factory=lambda: [])
    class_urls: List[str] = field(default_factory=lambda: [])


# ============================================================================
# Interfaces (Protocols) - Following ISP
# ============================================================================

class IBrowserContext(Protocol):
    """Interface for browser context management."""
    
    def create_context(self, storage_state: Optional[str] = None) -> Any:
        """Create a new browser context."""
        ...
    
    def close(self) -> None:
        """Close the browser."""
        ...


class IAuthenticator(Protocol):
    """Interface for authentication - Single Responsibility."""
    
    def login(self, username: str, password: str) -> bool:
        """Perform login and return success status."""
        ...
    
    def is_authenticated(self) -> bool:
        """Check if current session is authenticated."""
        ...
    
    def save_session(self, path: str) -> None:
        """Save current session to file."""
        ...
    
    def load_session(self, path: str) -> bool:
        """Load session from file. Returns True if successful."""
        ...


class ILibraryScraper(Protocol):
    """Interface for library navigation and discovery."""
    
    def get_user_sets(self) -> List[FlashCardSet]:
        """Get all flashcard sets from user's library."""
        ...
    
    def get_shared_sets(self) -> List[FlashCardSet]:
        """Get sets shared with the user."""
        ...
    
    def get_class_sets(self, class_url: str) -> List[FlashCardSet]:
        """Get sets from a specific class."""
        ...


class ISetScraper(Protocol):
    """Interface for scraping individual flashcard sets."""
    
    def scrape_set(self, set_url: str) -> FlashCardSet:
        """Scrape a single flashcard set by URL."""
        ...
    
    def scrape_sets(self, set_urls: List[str]) -> List[FlashCardSet]:
        """Scrape multiple flashcard sets."""
        ...


class IExporter(Protocol):
    """Interface for exporting data - Open/Closed Principle."""
    
    def export(self, flashcard_set: FlashCardSet, output_path: str) -> str:
        """Export a flashcard set to file. Returns the output file path."""
        ...
    
    def export_multiple(self, sets: List[FlashCardSet], output_dir: str) -> List[str]:
        """Export multiple sets. Returns list of output file paths."""
        ...
    
    @property
    def file_extension(self) -> str:
        """Get the file extension for this exporter."""
        ...


class IConfigLoader(Protocol):
    """Interface for configuration loading."""
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by key (supports dot notation)."""
        ...
    
    def reload(self) -> None:
        """Reload configuration from source."""
        ...


# ============================================================================
# Abstract Base Classes (for shared implementation)
# ============================================================================

class BaseExporter(ABC):
    """
    Abstract base class for exporters.
    Follows Template Method pattern for common export logic.
    """
    
    @property
    @abstractmethod
    def file_extension(self) -> str:
        """Get the file extension for this exporter."""
        pass
    
    @abstractmethod
    def _serialize(self, flashcard_set: FlashCardSet) -> str:
        """Serialize flashcard set to string format."""
        pass
    
    def export(self, flashcard_set: FlashCardSet, output_path: str) -> str:
        """Export a flashcard set to file."""
        import os
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        
        # Add extension if not present
        if not output_path.endswith(self.file_extension):
            output_path = f"{output_path}{self.file_extension}"
        
        # Serialize and write
        content: str = self._serialize(flashcard_set)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        return output_path
    
    def export_multiple(self, sets: List[FlashCardSet], output_dir: str) -> List[str]:
        """Export multiple sets to a directory."""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        output_paths: List[str] = []
        
        for flashcard_set in sets:
            # Sanitize filename
            safe_title: str = self._sanitize_filename(flashcard_set.title)
            filename: str = f"{flashcard_set.set_id}_{safe_title}"
            output_path: str = os.path.join(output_dir, filename)
            
            result_path: str = self.export(flashcard_set, output_path)
            output_paths.append(result_path)
        
        return output_paths
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize string for use as filename."""
        import re
        # Remove invalid characters
        sanitized: str = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        sanitized: str = sanitized.replace(' ', '_')
        # Limit length
        return sanitized[:50]
