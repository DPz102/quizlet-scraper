"""
Set scraper for extracting flashcard content.
Following Single Responsibility Principle - only extracts card data.
"""

import re
import json
import logging
from typing import List, Optional, Dict, Any
from playwright.sync_api import BrowserContext, Page, Response, Locator

from src.core.interfaces import FlashCard, FlashCardSet
from src.core.exceptions import SetNotFoundError, AccessDeniedError, ScrapingError
from src.scraper.base_scraper import BaseScraper

logger: logging.Logger = logging.getLogger(__name__)


class SetScraper(BaseScraper):
    """
    Scrapes individual flashcard sets to extract all cards.
    Single Responsibility: Card data extraction only.
    
    Uses two strategies:
    1. API Interception (preferred) - Captures internal API responses
    2. DOM Scraping (fallback) - Parses HTML directly
    """
    
    QUIZLET_BASE_URL = "https://quizlet.com"
    
    def __init__(
        self,
        context: BrowserContext,
        delay_min: float = 2.0,
        delay_max: float = 5.0,
        max_retries: int = 3,
        prefer_api: bool = True
    ) -> None:
        """
        Initialize set scraper.
        
        Args:
            context: Playwright browser context.
            delay_min: Minimum delay between requests.
            delay_max: Maximum delay between requests.
            max_retries: Maximum retry attempts.
            prefer_api: Whether to prefer API interception over DOM scraping.
        """
        super().__init__(context, delay_min, delay_max, max_retries)
        self._prefer_api: bool = prefer_api
        self._captured_data: Optional[Dict[str, Any]] = None
    
    def scrape_set(self, set_url: str) -> FlashCardSet:
        """
        Scrape a single flashcard set.
        
        Args:
            set_url: URL of the flashcard set.
            
        Returns:
            FlashCardSet with all cards populated.
            
        Raises:
            SetNotFoundError: If set doesn't exist.
            AccessDeniedError: If access is denied.
        """
        logger.info(f"Scraping set: {set_url}")
        
        # Reset captured data
        self._captured_data = None
        
        page: Page = self._get_page()
        
        # Set up API interception if preferred
        if self._prefer_api:
            page.on("response", self._handle_response)
        
        try:
            # Navigate to set
            page.goto(set_url, wait_until="networkidle")
            self._random_delay()
            
            # Check for errors
            self._check_for_errors(page)
            
            # Try API data first
            if self._prefer_api and self._captured_data:
                logger.info("Using API data for extraction")
                return self._parse_api_data(self._captured_data, set_url)
            
            # Fallback to DOM scraping
            logger.info("Using DOM scraping for extraction")
            return self._scrape_from_dom(page, set_url)
            
        except (SetNotFoundError, AccessDeniedError):
            raise
        except Exception as e:
            raise ScrapingError(f"Failed to scrape set: {str(e)}")
        finally:
            # Remove listener
            if self._prefer_api:
                try:
                    page.remove_listener("response", self._handle_response)
                except:
                    pass
    
    def scrape_sets(self, set_urls: List[str]) -> List[FlashCardSet]:
        """
        Scrape multiple flashcard sets.
        
        Args:
            set_urls: List of set URLs to scrape.
            
        Returns:
            List of FlashCardSet objects.
        """
        results: List[FlashCardSet] = []
        
        for i, url in enumerate(set_urls, 1):
            logger.info(f"Scraping set {i}/{len(set_urls)}: {url}")
            try:
                flash_set: FlashCardSet = self.scrape_set(url)
                results.append(flash_set)
                logger.info(f"Successfully scraped: {flash_set.title} ({len(flash_set.cards)} cards)")
            except Exception as e:
                logger.error(f"Failed to scrape {url}: {str(e)}")
                continue
        
        return results
    
    def _handle_response(self, response: Response) -> None:
        """Handle intercepted API responses."""
        try:
            url: str = response.url
            
            # Look for set data API endpoints
            if "/webapi/" in url and response.status == 200:
                content_type: str = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = response.json()
                        
                        # Check if this contains flashcard data
                        if self._is_flashcard_data(data):
                            logger.debug(f"Captured flashcard data from: {url}")
                            self._captured_data = data
                    except:
                        pass
        except:
            pass
    
    def _is_flashcard_data(self, data: Any) -> bool:
        """Check if data contains flashcard information."""
        if not isinstance(data, dict):
            return False
        
        # Look for common flashcard data patterns
        indicators: List[str] = ["studiableItem", "terms", "cards", "studiableData"]
        
        def search_dict(d: Dict[str, Any], depth: int = 0) -> bool:
            if depth > 3:
                return False
            for key, value in d.items():
                if key in indicators:
                    return True
                if isinstance(value, dict):
                    if search_dict(value, depth + 1):
                        return True
            return False
        
        return search_dict(data)
    
    def _parse_api_data(self, data: Dict[str, Any], set_url: str) -> FlashCardSet:
        """Parse flashcard data from API response."""
        cards: List[FlashCard] = []
        title = "Untitled Set"
        set_id: str | None = self._extract_set_id(set_url)
        description: Optional[str] = None
        created_by: Optional[str] = None
        
        # Navigate through nested structure to find cards
        def find_terms(obj: Any) -> List[Dict[str, Any]]:
            if isinstance(obj, list):
                # Check if this looks like a terms list
                if obj and isinstance(obj[0], dict):
                    if any(k in obj[0] for k in ["word", "term", "definition", "cardSides"]):
                        return obj
                # Recurse into list items
                for item in obj:
                    result = find_terms(item)
                    if result:
                        return result
            elif isinstance(obj, dict):
                # Check for direct terms
                for key in ["studiableItem", "terms", "cards"]:
                    if key in obj:
                        result = find_terms(obj[key])
                        if result:
                            return result
                # Get metadata
                if "title" in obj:
                    nonlocal title
                    title = obj.get("title", title)
                if "description" in obj:
                    nonlocal description
                    description = obj.get("description")
                if "creator" in obj and isinstance(obj["creator"], dict):
                    nonlocal created_by
                    created_by = obj["creator"].get("username")
                # Recurse into dict values
                for value in obj.values():
                    result = find_terms(value)
                    if result:
                        return result
            return []
        
        terms_data = find_terms(data)
        
        for term in terms_data:
            try:
                card: FlashCard | None = self._parse_term(term)
                if card:
                    cards.append(card)
            except Exception as e:
                logger.debug(f"Failed to parse term: {str(e)}")
                continue
        
        return FlashCardSet(
            set_id=set_id or "unknown",
            title=title,
            url=set_url,
            cards=cards,
            description=description,
            created_by=created_by,
            term_count=len(cards)
        )
    
    def _parse_term(self, term: Dict[str, Any]) -> Optional[FlashCard]:
        """Parse a single term from API data."""
        term_text: Optional[str] = None
        definition_text: Optional[str] = None
        term_id: Optional[str] = None
        image_url: Optional[str] = None
        
        # Handle different API response structures
        
        # Structure 1: cardSides format
        if "cardSides" in term:
            sides = term["cardSides"]
            for side in sides:
                label = side.get("label", "")
                media = side.get("media", [])
                
                for m in media:
                    if m.get("type") == "text":
                        text = m.get("plainText", "")
                        if label == "word":
                            term_text = text
                        elif label == "definition":
                            definition_text = text
                    elif m.get("type") == "image":
                        image_url = m.get("url")
        
        # Structure 2: Direct word/definition
        if not term_text:
            term_text = term.get("word") or term.get("term") or term.get("front")
        if not definition_text:
            definition_text = term.get("definition") or term.get("back")
        
        # Get term ID
        term_id = str(term.get("id", term.get("termId", "")))
        
        # Get image if not already found
        if not image_url:
            image_url = term.get("image") or term.get("imageUrl") or term.get("_imageUrl")
        
        if term_text and definition_text:
            return FlashCard(
                term=term_text.strip(),
                definition=definition_text.strip(),
                term_id=term_id or None,
                image_url=image_url
            )
        
        return None
    
    def _scrape_from_dom(self, page: Page, set_url: str) -> FlashCardSet:
        """Fallback: Scrape flashcard data from DOM."""
        cards: List[FlashCard] = []
        
        # Get set title
        title = "Untitled Set"
        try:
            title_elem: Locator = page.locator('h1, [class*="SetTitle"]').first
            if title_elem.is_visible(timeout=3000):
                title = title_elem.inner_text().strip()
        except:
            pass
        
        # Extract set ID
        set_id: str | None = self._extract_set_id(set_url)
        
        # Try to find and click "See all" or expand button to show all terms
        try:
            expand_btns: List[Locator] = page.locator('button:has-text("See all"), button:has-text("Xem tất cả")').all()
            for btn in expand_btns:
                if btn.is_visible():
                    btn.click()
                    self._random_delay()
                    break
        except:
            pass
        
        # Scroll to load all content
        self._scroll_to_bottom(page)
        
        # Various selectors for term/definition pairs
        selectors: List[Dict[str, str]] = [
            # Modern Quizlet structure
            {
                "container": '[class*="SetPageTerm"]',
                "term": '[class*="TermText"]',
                "definition": '[class*="DefinitionText"]'
            },
            # Alternative structure
            {
                "container": '.SetPageTerms-term',
                "term": '.TermText',
                "definition": '.DefinitionText'
            },
            # Simpler structure
            {
                "container": '[class*="term-"]',
                "term": '[class*="word"]',
                "definition": '[class*="definition"]'
            }
        ]
        
        for sel in selectors:
            try:
                containers: List[Locator] = page.locator(sel["container"]).all()
                
                if not containers:
                    continue
                
                for container in containers:
                    try:
                        term_elem: Locator = container.locator(sel["term"]).first
                        def_elem: Locator = container.locator(sel["definition"]).first
                        
                        term_text: str = term_elem.inner_text().strip() if term_elem.is_visible() else ""
                        def_text: str = def_elem.inner_text().strip() if def_elem.is_visible() else ""
                        
                        if term_text and def_text:
                            # Try to get image
                            image_url: Optional[str] = None
                            try:
                                img: Locator = container.locator("img").first
                                if img.is_visible():
                                    image_url = img.get_attribute("src")
                            except:
                                pass
                            
                            cards.append(FlashCard(
                                term=term_text,
                                definition=def_text,
                                image_url=image_url
                            ))
                    except:
                        continue
                
                if cards:
                    break
                    
            except Exception as e:
                logger.debug(f"Selector {sel} failed: {str(e)}")
                continue
        
        # If still no cards, try JavaScript extraction
        if not cards:
            cards = self._extract_via_javascript(page)
        
        return FlashCardSet(
            set_id=set_id or "unknown",
            title=title,
            url=set_url,
            cards=cards,
            term_count=len(cards)
        )
    
    def _extract_via_javascript(self, page: Page) -> List[FlashCard]:
        """Extract cards via JavaScript execution."""
        cards: List[FlashCard] = []
        
        try:
            # Try to find Quizlet's internal data
            script = """
            () => {
                // Look for window.__NEXT_DATA__ or similar
                if (window.__NEXT_DATA__ && window.__NEXT_DATA__.props) {
                    return JSON.stringify(window.__NEXT_DATA__.props);
                }
                
                // Look for Quizlet global
                if (window.Quizlet && window.Quizlet.setPageData) {
                    return JSON.stringify(window.Quizlet.setPageData);
                }
                
                return null;
            }
            """
            
            result = page.evaluate(script)
            if result:
                data = json.loads(result)
                # Parse the extracted data
                api_set: FlashCardSet = self._parse_api_data(data, page.url)
                return api_set.cards
                
        except Exception as e:
            logger.debug(f"JavaScript extraction failed: {str(e)}")
        
        return cards
    
    def _check_for_errors(self, page: Page) -> None:
        """Check for error conditions on the page."""
        url: str = page.url
        
        # Check for 404
        if "/404" in url or page.locator('text="Page not found"').is_visible(timeout=1000):
            raise SetNotFoundError("Flashcard set not found")
        
        # Check for access denied
        if "/login" in url:
            raise AccessDeniedError("Authentication required")
        
        # Check for private set message
        try:
            if page.locator('text="This set is private"').is_visible(timeout=1000):
                raise AccessDeniedError("This set is private")
        except:
            pass
    
    def _extract_set_id(self, url: str) -> Optional[str]:
        """Extract set ID from URL."""
        patterns: List[str] = [
            r'/(\d+)/[^/]+-flash-cards',
            r'/set/(\d+)',
            r'/(\d+)/'
        ]
        
        for pattern in patterns:
            match: re.Match[str] | None = re.search(pattern, url)
            if match:
                return match.group(1)
        
        return None
