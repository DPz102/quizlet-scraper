"""
Quizlet Scraper - Main Application Orchestrator.
Follows Dependency Injection pattern for loose coupling.
"""

import os
import sys
import argparse
import logging
from typing import List, Optional
from getpass import getpass

from src.utils.config import ConfigLoader
from src.utils.logging_config import setup_logging
from src.auth.browser_manager import BrowserManager, BrowserConfig
from src.auth.authenticator import QuizletAuthenticator
from src.scraper.library_scraper import LibraryScraper
from src.scraper.set_scraper import SetScraper
from src.export.exporter_factory import ExporterFactory
from src.core.interfaces import FlashCardSet
from src.core.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    SessionNotFoundError
)

logger = logging.getLogger(__name__)


class QuizletScraper:
    """
    Main application orchestrator.
    Uses Dependency Injection for all components.
    """
    
    def __init__(self, config: ConfigLoader):
        """
        Initialize the scraper with configuration.
        
        Args:
            config: Configuration loader instance.
        """
        self._config = config
        self._browser_manager: Optional[BrowserManager] = None
        self._authenticator: Optional[QuizletAuthenticator] = None
        self._library_scraper: Optional[LibraryScraper] = None
        self._set_scraper: Optional[SetScraper] = None
    
    def _create_browser_manager(self) -> BrowserManager:
        """Create browser manager with config."""
        browser_config = BrowserConfig(
            headless=self._config.get("browser.headless", False),
            slow_mo=self._config.get("browser.slow_mo", 100),
            timeout=self._config.get("browser.timeout", 30000)
        )
        return BrowserManager(browser_config)
    
    def login(self, username: str, password: str, save_session: bool = True) -> bool:
        """
        Perform login to Quizlet.
        
        Args:
            username: Quizlet username or email.
            password: Quizlet password.
            save_session: Whether to save session for reuse.
            
        Returns:
            True if login successful.
        """
        logger.info("Starting login process...")
        
        self._browser_manager = self._create_browser_manager()
        self._browser_manager.start()
        
        context = self._browser_manager.create_context()
        self._authenticator = QuizletAuthenticator(context)
        
        success = self._authenticator.login(username, password)
        
        if success and save_session:
            session_path = self._config.session_path
            self._authenticator.save_session(session_path)
            logger.info(f"Session saved to: {session_path}")
        
        return success
    
    def login_with_session(self) -> bool:
        """
        Login using saved session.
        
        Returns:
            True if session is valid.
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
    
    def discover_sets(self, include_shared: bool = True) -> List[FlashCardSet]:
        """
        Discover all flashcard sets available to the user.
        
        Args:
            include_shared: Whether to include shared sets from classes.
            
        Returns:
            List of FlashCardSet objects (metadata only).
        """
        if self._authenticator is None:
            raise AuthenticationError("Not logged in")
        
        context = self._authenticator._context
        
        self._library_scraper = LibraryScraper(
            context=context,
            delay_min=self._config.get("scraper.delay_min", 2.0),
            delay_max=self._config.get("scraper.delay_max", 5.0),
            max_retries=self._config.get("scraper.max_retries", 3)
        )
        
        # Get user's own sets
        all_sets = self._library_scraper.get_user_sets()
        
        # Get shared sets
        if include_shared:
            shared_sets = self._library_scraper.get_shared_sets()
            # Merge and deduplicate
            seen_ids = {s.set_id for s in all_sets}
            for s in shared_sets:
                if s.set_id not in seen_ids:
                    all_sets.append(s)
                    seen_ids.add(s.set_id)
        
        return all_sets
    
    def scrape_sets(self, set_urls: List[str]) -> List[FlashCardSet]:
        """
        Scrape flashcard content from given URLs.
        
        Args:
            set_urls: List of set URLs to scrape.
            
        Returns:
            List of FlashCardSet objects with cards.
        """
        if self._authenticator is None:
            raise AuthenticationError("Not logged in")
        
        context = self._authenticator._context
        
        self._set_scraper = SetScraper(
            context=context,
            delay_min=self._config.get("scraper.delay_min", 2.0),
            delay_max=self._config.get("scraper.delay_max", 5.0),
            max_retries=self._config.get("scraper.max_retries", 3)
        )
        
        return self._set_scraper.scrape_sets(set_urls)
    
    def scrape_single_set(self, set_url: str) -> FlashCardSet:
        """
        Scrape a single flashcard set.
        
        Args:
            set_url: URL of the set to scrape.
            
        Returns:
            FlashCardSet with cards.
        """
        sets = self.scrape_sets([set_url])
        if sets:
            return sets[0]
        raise ValueError(f"Failed to scrape set: {set_url}")
    
    def export(
        self,
        sets: List[FlashCardSet],
        formats: Optional[List[str]] = None,
        output_dir: Optional[str] = None
    ) -> List[str]:
        """
        Export scraped flashcard sets.
        
        Args:
            sets: List of FlashCardSet objects to export.
            formats: List of export formats (default from config).
            output_dir: Output directory (default from config).
            
        Returns:
            List of exported file paths.
        """
        formats = formats or self._config.get("export.formats", ["json"])
        output_dir = output_dir or self._config.get("export.output_dir", "output")
        
        os.makedirs(output_dir, exist_ok=True)
        
        all_paths = []
        
        for format_str in formats:
            try:
                exporter = ExporterFactory.create_from_string(
                    format_str,
                    include_images=self._config.get("export.include_images", False)
                )
                
                format_dir = os.path.join(output_dir, format_str)
                paths = exporter.export_multiple(sets, format_dir)
                all_paths.extend(paths)
                
                logger.info(f"Exported {len(sets)} sets to {format_str} format")
                
            except Exception as e:
                logger.error(f"Failed to export to {format_str}: {str(e)}")
        
        return all_paths
    
    def run_full_pipeline(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        set_urls: Optional[List[str]] = None
    ) -> List[str]:
        """
        Run the full scraping pipeline.
        
        Args:
            username: Quizlet username (prompts if not provided).
            password: Quizlet password (prompts if not provided).
            set_urls: Specific set URLs to scrape (discovers if not provided).
            
        Returns:
            List of exported file paths.
        """
        try:
            # Step 1: Authentication
            try:
                self.login_with_session()
            except (SessionNotFoundError, SessionExpiredError):
                logger.info("No valid session, performing login...")
                
                if not username:
                    username = input("Quizlet username/email: ")
                if not password:
                    password = getpass("Quizlet password: ")
                
                self.login(username, password)
            
            # Step 2: Discover or use provided URLs
            if set_urls:
                logger.info(f"Scraping {len(set_urls)} specified sets...")
            else:
                logger.info("Discovering available flashcard sets...")
                discovered = self.discover_sets()
                set_urls = [s.url for s in discovered]
                logger.info(f"Found {len(set_urls)} sets to scrape")
            
            if not set_urls:
                logger.warning("No sets found to scrape")
                return []
            
            # Step 3: Scrape sets
            logger.info("Scraping flashcard content...")
            scraped_sets = self.scrape_sets(set_urls)
            logger.info(f"Successfully scraped {len(scraped_sets)} sets")
            
            # Step 4: Export
            logger.info("Exporting scraped data...")
            exported_paths = self.export(scraped_sets)
            
            logger.info(f"Export complete! {len(exported_paths)} files created")
            return exported_paths
            
        finally:
            self.close()
    
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


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Quizlet Private Flashcard Scraper"
    )
    
    parser.add_argument(
        "-u", "--username",
        help="Quizlet username or email"
    )
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "-s", "--sets",
        nargs="*",
        help="Specific set URLs to scrape"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output directory"
    )
    parser.add_argument(
        "-f", "--formats",
        nargs="*",
        choices=["json", "csv", "tsv", "anki"],
        help="Export formats"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser in headless mode"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    
    # Load config
    config = ConfigLoader(args.config)
    
    # Override config with CLI args
    if args.headless:
        config._config["browser"]["headless"] = True
    if args.output:
        config._config["export"]["output_dir"] = args.output
    if args.formats:
        config._config["export"]["formats"] = args.formats
    
    # Run scraper
    scraper = QuizletScraper(config)
    
    try:
        password = None
        if args.username:
            password = getpass("Quizlet password: ")
        
        exported = scraper.run_full_pipeline(
            username=args.username,
            password=password,
            set_urls=args.sets
        )
        
        if exported:
            print(f"\n✅ Success! Exported {len(exported)} files:")
            for path in exported[:10]:
                print(f"   - {path}")
            if len(exported) > 10:
                print(f"   ... and {len(exported) - 10} more")
        else:
            print("\n⚠️ No files exported")
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except AuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("An error occurred")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
