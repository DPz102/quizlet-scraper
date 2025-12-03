"""
Scraper service containing business logic.
Following Single Responsibility Principle - handles scraping operations only.
Separates business logic from CLI concerns.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from getpass import getpass
from typing import Any

from playwright.sync_api import BrowserContext

from src.auth.authenticator import QuizletAuthenticator
from src.auth.browser_manager import BrowserConfig, BrowserManager
from src.core.exceptions import SessionExpiredError, SessionNotFoundError
from src.core.interfaces import FlashCardSet
from src.export.quizlet_exporter import QuizletExporter
from src.scraper.library_scraper import LibraryScraper
from src.scraper.set_scraper import SetScraper
from src.utils.config import ConfigLoader

logger: logging.Logger = logging.getLogger(__name__)


class ScraperService:
    """
    Main service for scraping operations.
    Orchestrates authentication, scraping, and export components.
    """
    
    METADATA_FILE = "sets_metadata.json"
    
    def __init__(self, config: ConfigLoader) -> None:
        """
        Initialize the scraper service.
        
        Args:
            config: Configuration loader instance.
        """
        self._config = config
        self._browser_manager: BrowserManager | None = None
        self._authenticator: QuizletAuthenticator | None = None
        self._library_scraper: LibraryScraper | None = None
        self._set_scraper: SetScraper | None = None
    
    # =========================================================================
    # Authentication Methods
    # =========================================================================
    
    def manual_login(self, timeout: int = 300) -> bool:
        """
        Open browser for manual login (supports Google OAuth).
        
        Args:
            timeout: Maximum time to wait for login in seconds.
            
        Returns:
            True if login successful.
        """
        logger.info("Starting manual login process...")
        
        self._browser_manager = self._create_browser_manager(headless=False)
        self._browser_manager.start()
        
        context = self._browser_manager.create_context()
        self._authenticator = QuizletAuthenticator(context)
        
        success = self._authenticator.manual_login(timeout=timeout)
        
        if success:
            session_path = self._config.session_path
            self._authenticator.save_session(session_path)
            logger.info(f"Session saved to: {session_path}")
        
        return success
    
    def login(self, username: str, password: str) -> bool:
        """
        Perform login with username/password.
        
        Args:
            username: Quizlet username or email.
            password: Quizlet password.
            
        Returns:
            True if login successful.
        """
        logger.info("Starting login process...")
        
        self._browser_manager = self._create_browser_manager()
        self._browser_manager.start()
        
        context = self._browser_manager.create_context()
        self._authenticator = QuizletAuthenticator(context)
        
        success = self._authenticator.login(username, password)
        
        if success:
            session_path = self._config.session_path
            self._authenticator.save_session(session_path)
            logger.info(f"Session saved to: {session_path}")
        
        return success
    
    def login_with_session(self) -> bool:
        """
        Login using saved session.
        
        Returns:
            True if session is valid.
            
        Raises:
            SessionNotFoundError: If no session file exists.
            SessionExpiredError: If session has expired.
        """
        session_path = self._config.session_path
        
        if not os.path.exists(session_path):
            raise SessionNotFoundError(f"No saved session found at: {session_path}")
        
        logger.info(f"Loading session from: {session_path}")
        
        self._browser_manager = self._create_browser_manager()
        self._browser_manager.start()
        
        context = self._browser_manager.create_context(storage_state=session_path)
        self._authenticator = QuizletAuthenticator(context)
        
        if self._authenticator.is_authenticated():
            logger.info("Session is valid, logged in successfully")
            return True
        else:
            raise SessionExpiredError("Saved session has expired")
    
    def logout(self) -> None:
        """Clear saved session."""
        session_path = self._config.session_path
        
        if os.path.exists(session_path):
            os.remove(session_path)
            logger.info(f"Session removed: {session_path}")
        else:
            logger.info("No session to remove")
    
    # =========================================================================
    # Discovery Methods
    # =========================================================================
    
    def discover(
        self,
        username: str | None = None,
        manual_login: bool = False
    ) -> list[FlashCardSet]:
        """
        Discover all flashcard sets and save metadata.
        
        Args:
            username: Quizlet username (prompts if needed).
            manual_login: Use manual browser login instead of credentials.
            
        Returns:
            List of discovered FlashCardSet objects.
        """
        try:
            # Try existing session first
            self._ensure_authenticated(username, manual_login)
            
            # Create library scraper
            assert self._authenticator is not None
            context = self._authenticator.context
            
            self._library_scraper = LibraryScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            logger.info("Discovering flashcard sets...")
            
            # Get user's own sets
            all_sets = self._library_scraper.get_user_sets()
            
            # Get shared sets
            shared_sets = self._library_scraper.get_shared_sets()
            
            # Merge and deduplicate
            seen_ids: set[str] = {s.set_id for s in all_sets}
            for s in shared_sets:
                if s.set_id not in seen_ids:
                    all_sets.append(s)
                    seen_ids.add(s.set_id)
            
            # Save metadata
            metadata_path = self._save_metadata(all_sets)
            logger.info(f"Metadata saved to: {metadata_path}")
            
            return all_sets
            
        finally:
            self.close()
    
    # =========================================================================
    # Scraping Methods
    # =========================================================================
    
    def scrape_by_id(self, set_id: str) -> FlashCardSet | None:
        """
        Scrape a single set by ID.
        
        Args:
            set_id: The set ID to scrape.
            
        Returns:
            FlashCardSet with cards, or None if not found.
        """
        set_info = self._find_set_in_metadata(set_id)
        
        if not set_info:
            logger.error(f"Set ID {set_id} not found in metadata")
            return None
        
        return self.scrape_by_url(set_info["url"])
    
    def scrape_by_url(self, url: str) -> FlashCardSet | None:
        """
        Scrape a single set by URL.
        
        Args:
            url: The set URL to scrape.
            
        Returns:
            FlashCardSet with cards.
        """
        try:
            self.login_with_session()
            
            assert self._authenticator is not None
            context = self._authenticator.context
            
            self._set_scraper = SetScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            flash_set = self._set_scraper.scrape_set(url)
            self._export_set(flash_set)
            
            return flash_set
            
        finally:
            self.close()
    
    def scrape_all(self) -> list[FlashCardSet]:
        """
        Scrape all sets from metadata.
        
        Returns:
            List of FlashCardSet with cards.
        """
        metadata = self._load_metadata()
        sets_info = metadata.get("sets", [])
        
        if not sets_info:
            logger.warning("No sets in metadata")
            return []
        
        try:
            self.login_with_session()
            
            assert self._authenticator is not None
            context = self._authenticator.context
            
            self._set_scraper = SetScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            results: list[FlashCardSet] = []
            urls = [s["url"] for s in sets_info]
            
            for i, url in enumerate(urls, 1):
                logger.info(f"Scraping set {i}/{len(urls)}")
                try:
                    flash_set = self._set_scraper.scrape_set(url)
                    results.append(flash_set)
                    self._export_set(flash_set)
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")
                    continue
            
            return results
            
        finally:
            self.close()
    
    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _create_browser_manager(self, headless: bool | None = None) -> BrowserManager:
        """Create browser manager with config."""
        browser_config = BrowserConfig(
            headless=headless if headless is not None else self._config.get("browser.headless", False),
            slow_mo=self._config.get("browser.slow_mo", 100),
            timeout=self._config.get("browser.timeout", 30000)
        )
        return BrowserManager(browser_config)
    
    def _ensure_authenticated(
        self,
        username: str | None = None,
        manual_login: bool = False
    ) -> None:
        """
        Ensure user is authenticated, prompting if needed.
        
        Args:
            username: Optional username for credential login.
            manual_login: Use manual browser login.
        """
        try:
            self.login_with_session()
        except (SessionNotFoundError, SessionExpiredError):
            logger.info("No valid session, performing login...")
            
            if manual_login:
                # Close existing browser if any
                if self._browser_manager:
                    self._browser_manager.close()
                    self._browser_manager = None
                
                self.manual_login()
            else:
                if not username:
                    username = input("Quizlet username/email: ")
                password = getpass("Quizlet password: ")
                self.login(username, password)
    
    def _get_metadata_path(self) -> str:
        """Get path to metadata file."""
        output_dir = self._config.get("export.output_dir", "output")
        return os.path.join(output_dir, self.METADATA_FILE)
    
    def _save_metadata(self, sets: list[FlashCardSet]) -> str:
        """Save discovered sets metadata to file."""
        output_dir = self._config.get("export.output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        metadata: dict[str, Any] = {
            "discovered_at": datetime.now().isoformat(),
            "total_sets": len(sets),
            "sets": [
                {
                    "set_id": s.set_id,
                    "title": s.title,
                    "url": s.url,
                    "term_count": s.term_count,
                    "description": s.description,
                    "created_by": s.created_by
                }
                for s in sets
            ]
        }
        
        path = self._get_metadata_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return path
    
    def _load_metadata(self) -> dict[str, Any]:
        """Load metadata from file."""
        path = self._get_metadata_path()
        
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Metadata file not found: {path}\n"
                "Run 'discover' command first."
            )
        
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    
    def _find_set_in_metadata(self, set_id: str) -> dict[str, Any] | None:
        """Find a set by ID in metadata."""
        metadata = self._load_metadata()
        for s in metadata.get("sets", []):
            if s["set_id"] == set_id:
                return s
        return None
    
    def _export_set(self, flash_set: FlashCardSet) -> str:
        """Export a single set to Quizlet-compatible format."""
        output_dir = self._config.get("export.output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        exporter = QuizletExporter()
        path = exporter.export(flash_set, output_dir)
        
        logger.info(f"Exported: {path}")
        return path
    
    def close(self) -> None:
        """Cleanup resources."""
        if self._set_scraper:
            self._set_scraper.close()
        if self._library_scraper:
            self._library_scraper.close()
        if self._authenticator:
            self._authenticator.close()
        if self._browser_manager:
            self._browser_manager.close()
