"""
Quizlet-compatible exporter using custom tags.
Format designed for direct import into Quizlet.

Import settings in Quizlet:
- Between term and definition: /answer/
- Between cards: /question/
"""

import os
import re
import logging
from typing import List

from src.core.interfaces import FlashCard, FlashCardSet

logger: logging.Logger = logging.getLogger(__name__)


class QuizletExporter:
    """
    Exports flashcard sets to Quizlet-importable format.
    
    Format:
        /question/term1/answer/definition1/question/term2/answer/definition2
    
    This format uses custom tags to avoid conflicts with actual content.
    """
    
    QUESTION_TAG = "/question/"
    ANSWER_TAG = "/answer/"
    IMAGE_TAG = "/image/"
    
    def __init__(self, include_images: bool = True) -> None:
        """
        Initialize exporter.
        
        Args:
            include_images: Whether to include image URLs in export.
        """
        self._include_images: bool = include_images
    
    def export(self, flashcard_set: FlashCardSet, output_dir: str) -> str:
        """
        Export a flashcard set to file.
        
        Args:
            flashcard_set: The flashcard set to export.
            output_dir: Directory to save the file.
            
        Returns:
            Path to the exported file.
        """
        os.makedirs(output_dir, exist_ok=True)
        
        # Sanitize filename
        safe_title: str = self._sanitize_filename(flashcard_set.title)
        filename: str = f"export_{flashcard_set.set_id}_{safe_title}.txt"
        filepath: str = os.path.join(output_dir, filename)
        
        # Build content
        content: str = self._serialize(flashcard_set)
        
        # Write file
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        logger.info(f"Exported {len(flashcard_set.cards)} cards to: {filepath}")
        return filepath
    
    def export_multiple(self, sets: List[FlashCardSet], output_dir: str) -> List[str]:
        """
        Export multiple flashcard sets.
        
        Args:
            sets: List of flashcard sets to export.
            output_dir: Directory to save files.
            
        Returns:
            List of exported file paths.
        """
        paths: List[str] = []
        for flash_set in sets:
            try:
                path = self.export(flash_set, output_dir)
                paths.append(path)
            except Exception as e:
                logger.error(f"Failed to export {flash_set.title}: {e}")
        return paths
    
    def _serialize(self, flashcard_set: FlashCardSet) -> str:
        """
        Serialize flashcard set to export format.
        
        Args:
            flashcard_set: The flashcard set to serialize.
            
        Returns:
            Formatted string ready for Quizlet import.
        """
        lines: List[str] = []
        
        # Header comment (won't affect import)
        lines.append(f"# {flashcard_set.title}")
        lines.append(f"# Set ID: {flashcard_set.set_id}")
        lines.append(f"# Cards: {len(flashcard_set.cards)}")
        if flashcard_set.url:
            lines.append(f"# Source: {flashcard_set.url}")
        lines.append("#")
        lines.append("# Import settings for Quizlet:")
        lines.append("#   Between term and definition: /answer/")
        lines.append("#   Between cards: /question/")
        if self._include_images:
            lines.append("#   (Images are marked with /image/ tag)")
        lines.append("#")
        lines.append("")
        
        # Build cards string
        cards_parts: List[str] = []
        
        for card in flashcard_set.cards:
            # Clean term and definition (remove the tags if they somehow exist)
            term = self._escape_tags(card.term)
            definition = self._escape_tags(card.definition)
            
            # Build card entry
            if self._include_images and card.image_url:
                # Include image URL in definition
                card_str: str = f"{self.QUESTION_TAG}{term}{self.ANSWER_TAG}{definition}{self.IMAGE_TAG}{card.image_url}"
            else:
                card_str: str = f"{self.QUESTION_TAG}{term}{self.ANSWER_TAG}{definition}"
            
            cards_parts.append(card_str)
        
        # Join all cards (remove leading /question/ from first card for cleaner format)
        if cards_parts:
            # First card without leading /question/
            first_card = cards_parts[0][len(self.QUESTION_TAG):]
            rest_cards = cards_parts[1:]
            
            all_cards = first_card + "".join(rest_cards)
            lines.append(all_cards)
        
        return "\n".join(lines)
    
    def _escape_tags(self, text: str) -> str:
        """
        Escape any existing tags in the text to avoid conflicts.
        
        Args:
            text: Text to escape.
            
        Returns:
            Escaped text.
        """
        if not text:
            return ""
        
        # Replace literal tags with escaped versions
        text = text.replace("/question/", "//question//")
        text = text.replace("/answer/", "//answer//")
        text = text.replace("/image/", "//image//")
        
        # Remove newlines (replace with space)
        text = text.replace("\n", " ").replace("\r", "")
        
        return text.strip()
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """Sanitize string for use as filename."""
        # Remove invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace spaces with underscores
        sanitized = sanitized.replace(' ', '_')
        # Limit length
        return sanitized[:50]


def parse_quizlet_export(content: str) -> list[dict[str, object]]:
    """
    Parse exported content back to cards (for testing/verification).
    
    Args:
        content: Exported file content.
        
    Returns:
        List of card dictionaries.
    """
    cards: list[dict[str, object]] = []
    
    # Remove comment lines
    lines = [line for line in content.split("\n") if not line.startswith("#") and line.strip()]
    content = "\n".join(lines)
    
    if not content:
        return cards
    
    # Split by /question/ tag
    parts = content.split("/question/")
    
    for part in parts:
        if not part.strip():
            continue
        
        # Split by /answer/ tag
        if "/answer/" in part:
            term_part, rest = part.split("/answer/", 1)
            
            # Check for image
            if "/image/" in rest:
                definition, image_url = rest.split("/image/", 1)
            else:
                definition = rest
                image_url = None
            
            cards.append({
                "term": term_part.strip(),
                "definition": definition.strip(),
                "image_url": image_url.strip() if image_url else None
            })
    
    return cards
