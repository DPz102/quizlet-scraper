"""
Base scraper with common functionality.
Following Template Method pattern and DRY principle.
"""

import random
import time
import logging
from abc import ABC, abstractmethod
from typing import Optional
from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """
    Abstract base class for scrapers.
    Provides common functionality: delay, retry, page management.
    """
    
    def __init__(
        self,
        context: BrowserContext,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3
    ):
        """
        Initialize base scraper.
        
        Args:
            context: Playwright browser context.
            delay_min: Minimum delay between requests (seconds).
            delay_max: Maximum delay between requests (seconds).
            max_retries: Maximum retry attempts on failure.
        """
        self._context = context
        self._delay_min = delay_min
        self._delay_max = delay_max
        self._max_retries = max_retries
        self._page: Optional[Page] = None
    
    def _get_page(self) -> Page:
        """Get or create a page."""
        if self._page is None or self._page.is_closed():
            self._page = self._context.new_page()
        return self._page
    
    def _random_delay(self) -> None:
        """Apply random delay between requests (anti-detection)."""
        delay = random.uniform(self._delay_min, self._delay_max)
        logger.debug(f"Waiting {delay:.2f}s...")
        time.sleep(delay)
    
    def _navigate(self, url: str, wait_until: str = "networkidle") -> Page:
        """
        Navigate to URL with retry logic.
        
        Args:
            url: URL to navigate to.
            wait_until: Wait condition (load, domcontentloaded, networkidle).
            
        Returns:
            Page after navigation.
        """
        page = self._get_page()
        
        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(f"Navigating to: {url} (attempt {attempt})")
                page.goto(url, wait_until=wait_until)
                self._random_delay()
                return page
            except Exception as e:
                logger.warning(f"Navigation failed (attempt {attempt}): {str(e)}")
                if attempt == self._max_retries:
                    raise
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return page
    
    def _scroll_to_bottom(self, page: Optional[Page] = None) -> None:
        """Scroll to bottom of page to load lazy content."""
        p = page or self._get_page()
        
        # Get initial height
        last_height = p.evaluate("document.body.scrollHeight")
        
        while True:
            # Scroll down
            p.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1)
            
            # Calculate new height
            new_height = p.evaluate("document.body.scrollHeight")
            
            if new_height == last_height:
                break
            last_height = new_height
    
    def close(self) -> None:
        """Close the page."""
        if self._page and not self._page.is_closed():
            self._page.close()
            self._page = None
