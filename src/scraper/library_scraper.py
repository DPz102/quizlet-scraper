"""
Library scraper for discovering flashcard sets.
Following Single Responsibility Principle - only discovers sets.
"""

import re
import logging
from typing import List, Optional
from playwright.sync_api import BrowserContext, Locator

from src.core.interfaces import FlashCardSet
from src.core.exceptions import ScrapingError
from src.scraper.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class LibraryScraper(BaseScraper):
    """
    Scrapes user's library to discover flashcard sets.
    Single Responsibility: Discovery and listing only, not content extraction.
    """
    
    QUIZLET_LATEST_URL = "https://quizlet.com/latest"
    QUIZLET_BASE_URL = "https://quizlet.com"
    
    def __init__(
        self,
        context: BrowserContext,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3
    ):
        super().__init__(context, delay_min, delay_max, max_retries)
    
    def get_user_sets(self) -> List[FlashCardSet]:
        """
        Get all flashcard sets from user's library.
        
        Returns:
            List of FlashCardSet objects (without cards, just metadata).
        """
        logger.info("Fetching user's flashcard sets...")
        page = self._navigate(self.QUIZLET_LATEST_URL)
        
        # Scroll to load all sets
        self._scroll_to_bottom(page)
        
        sets = self._extract_sets_from_page(page)
        logger.info(f"Found {len(sets)} sets in user library")
        
        return sets
    
    def get_shared_sets(self) -> List[FlashCardSet]:
        """
        Get sets shared with the user (from classes, folders, etc.).
        
        Returns:
            List of FlashCardSet objects.
        """
        all_sets: List[FlashCardSet] = []
        
        # Get sets from user's classes
        classes = self._get_user_classes()
        for class_url in classes:
            try:
                class_sets = self.get_class_sets(class_url)
                all_sets.extend(class_sets)
            except Exception as e:
                logger.warning(f"Failed to get sets from class {class_url}: {str(e)}")
        
        return all_sets
    
    def get_class_sets(self, class_url: str) -> List[FlashCardSet]:
        """
        Get sets from a specific class.
        
        Args:
            class_url: URL of the class.
            
        Returns:
            List of FlashCardSet objects.
        """
        logger.info(f"Fetching sets from class: {class_url}")
        page = self._navigate(class_url)
        
        # Click on "Sets" tab if present
        try:
            sets_tab = page.locator('a:has-text("Sets"), button:has-text("Sets")').first
            if sets_tab.is_visible(timeout=3000):
                sets_tab.click()
                self._random_delay()
        except:
            pass
        
        self._scroll_to_bottom(page)
        sets = self._extract_sets_from_page(page)
        
        logger.info(f"Found {len(sets)} sets in class")
        return sets
    
    def get_folder_sets(self, folder_url: str) -> List[FlashCardSet]:
        """
        Get sets from a specific folder.
        
        Args:
            folder_url: URL of the folder.
            
        Returns:
            List of FlashCardSet objects.
        """
        logger.info(f"Fetching sets from folder: {folder_url}")
        page = self._navigate(folder_url)
        
        self._scroll_to_bottom(page)
        sets = self._extract_sets_from_page(page)
        
        logger.info(f"Found {len(sets)} sets in folder")
        return sets
    
    def _get_user_classes(self) -> List[str]:
        """Get URLs of classes the user is enrolled in."""
        logger.info("Discovering user's classes...")
        
        # Navigate to classes page
        page = self._navigate(f"{self.QUIZLET_BASE_URL}/latest")
        
        class_urls = []
        
        # Look for class links
        class_selectors = [
            'a[href*="/class/"]',
            '[class*="Class"] a',
        ]
        
        for selector in class_selectors:
            try:
                links = page.locator(selector).all()
                for link in links:
                    href = link.get_attribute("href")
                    if href and "/class/" in href:
                        full_url = href if href.startswith("http") else f"{self.QUIZLET_BASE_URL}{href}"
                        if full_url not in class_urls:
                            class_urls.append(full_url)
            except:
                continue
        
        logger.info(f"Found {len(class_urls)} classes")
        return class_urls
    
    def _extract_sets_from_page(self, page) -> List[FlashCardSet]:
        """
        Extract flashcard set information from current page.
        
        Args:
            page: Playwright page object.
            
        Returns:
            List of FlashCardSet objects (metadata only, no cards).
        """
        sets: List[FlashCardSet] = []
        
        # Various selectors for flashcard set links
        set_selectors = [
            'a[href*="-flash-cards"]',
            'a[href*="/set/"]',
            '[class*="SetPreview"] a',
            '[class*="DashboardListItem"] a',
        ]
        
        seen_urls = set()
        
        for selector in set_selectors:
            try:
                links = page.locator(selector).all()
                
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        if not href:
                            continue
                        
                        # Build full URL
                        full_url = href if href.startswith("http") else f"{self.QUIZLET_BASE_URL}{href}"
                        
                        # Skip if already processed
                        if full_url in seen_urls:
                            continue
                        seen_urls.add(full_url)
                        
                        # Extract set ID from URL
                        set_id = self._extract_set_id(full_url)
                        if not set_id:
                            continue
                        
                        # Get title
                        title = self._extract_title(link)
                        
                        # Get term count if available
                        term_count = self._extract_term_count(link)
                        
                        flash_set = FlashCardSet(
                            set_id=set_id,
                            title=title,
                            url=full_url,
                            term_count=term_count
                        )
                        sets.append(flash_set)
                        
                    except Exception as e:
                        logger.debug(f"Failed to extract set info: {str(e)}")
                        continue
                        
            except Exception as e:
                logger.debug(f"Selector {selector} failed: {str(e)}")
                continue
        
        return sets
    
    def _extract_set_id(self, url: str) -> Optional[str]:
        """Extract set ID from URL."""
        # Pattern: /123456789/set-name-flash-cards or /set/123456789
        patterns = [
            r'/(\d+)/[^/]+-flash-cards',
            r'/set/(\d+)',
            r'/(\d+)/'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_title(self, link: Locator) -> str:
        """Extract title from link element."""
        try:
            # Try to get text content
            text = link.inner_text()
            if text:
                return text.strip()
            
            # Try aria-label
            label = link.get_attribute("aria-label")
            if label:
                return label.strip()
            
            # Try title attribute
            title = link.get_attribute("title")
            if title:
                return title.strip()
                
        except:
            pass
        
        return "Untitled Set"
    
    def _extract_term_count(self, link: Locator) -> int:
        """Extract term count from nearby elements."""
        try:
            # Look for term count in parent or sibling elements
            parent = link.locator("..")
            text = parent.inner_text()
            
            # Look for patterns like "50 terms" or "50 thuật ngữ"
            match = re.search(r'(\d+)\s*(?:terms?|thuật ngữ|cards?|thẻ)', text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        except:
            pass
        
        return 0
