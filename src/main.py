"""
Quizlet Scraper - Main Application Orchestrator.
Follows Dependency Injection pattern for loose coupling.

Commands:
    discover  - Login and scan library, save metadata
    scrape    - Scrape specific set(s) using saved session
    logout    - Clear saved session
"""

import os
import sys
import argparse
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from getpass import getpass

from playwright.sync_api import BrowserContext

from playwright.sync_api._generated import BrowserContext

from playwright.sync_api._generated import BrowserContext

from src.utils.config import ConfigLoader
from src.utils.logging_config import setup_logging
from src.auth.browser_manager import BrowserManager, BrowserConfig
from src.auth.authenticator import QuizletAuthenticator
from src.scraper.library_scraper import LibraryScraper
from src.scraper.set_scraper import SetScraper
from src.export.quizlet_exporter import QuizletExporter
from src.core.interfaces import FlashCardSet
from src.core.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    SessionNotFoundError
)

logger: logging.Logger = logging.getLogger(__name__)


class QuizletScraper:
    """
    Main application orchestrator.
    Uses Dependency Injection for all components.
    """
    
    METADATA_FILE = "sets_metadata.json"
    
    def __init__(self, config: ConfigLoader) -> None:
        """
        Initialize the scraper with configuration.
        
        Args:
            config: Configuration loader instance.
        """
        self._config: ConfigLoader = config
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
    
    def _get_metadata_path(self) -> str:
        """Get path to metadata file."""
        output_dir = self._config.get("export.output_dir", "output")
        return os.path.join(output_dir, self.METADATA_FILE)
    
    def _save_metadata(self, sets: List[FlashCardSet]) -> str:
        """Save discovered sets metadata to file."""
        output_dir = self._config.get("export.output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        metadata: Dict[str, Any] = {
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
        
        path: str = self._get_metadata_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        return path
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load metadata from file."""
        path: str = self._get_metadata_path()
        
        if not os.path.exists(path):
            raise FileNotFoundError(
                f"Metadata file not found: {path}\n"
                "Run 'discover' command first."
            )
        
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _find_set_in_metadata(self, set_id: str) -> Optional[Dict[str, Any]]:
        """Find a set by ID in metadata."""
        metadata = self._load_metadata()
        for s in metadata.get("sets", []):
            if s["set_id"] == set_id:
                return s
        return None
    
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
        
        context: BrowserContext = self._browser_manager.create_context()
        self._authenticator = QuizletAuthenticator(context)
        
        success: bool = self._authenticator.login(username, password)
        
        if success and save_session:
            session_path: str = self._config.session_path
            self._authenticator.save_session(session_path)
            logger.info(f"Session saved to: {session_path}")
        
        return success
    
    def login_with_session(self) -> bool:
        """
        Login using saved session.
        
        Returns:
            True if session is valid.
        """
        session_path: str = self._config.session_path
        
        if not os.path.exists(session_path):
            raise SessionNotFoundError(f"No saved session found at: {session_path}")
        
        logger.info(f"Loading session from: {session_path}")
        
        self._browser_manager = self._create_browser_manager()
        self._browser_manager.start()
        
        context: BrowserContext = self._browser_manager.create_context(storage_state=session_path)
        self._authenticator = QuizletAuthenticator(context)
        
        if self._authenticator.is_authenticated():
            logger.info("Session is valid, logged in successfully")
            return True
        else:
            raise SessionExpiredError("Saved session has expired")
    
    def logout(self) -> None:
        """Clear saved session."""
        session_path: str = self._config.session_path
        
        if os.path.exists(session_path):
            os.remove(session_path)
            logger.info(f"Session removed: {session_path}")
        else:
            logger.info("No session to remove")
    
    def discover(self, username: Optional[str] = None, password: Optional[str] = None) -> List[FlashCardSet]:
        """
        Discover all flashcard sets and save metadata.
        
        Args:
            username: Quizlet username (prompts if needed).
            password: Quizlet password (prompts if needed).
            
        Returns:
            List of discovered FlashCardSet objects.
        """
        try:
            # Try existing session first
            try:
                self.login_with_session()
            except (SessionNotFoundError, SessionExpiredError):
                logger.info("No valid session, performing login...")
                
                if not username:
                    username = input("Quizlet username/email: ")
                if not password:
                    password = getpass("Quizlet password: ")
                
                self.login(username, password)
            
            # Discover sets
            assert self._authenticator is not None
            context: BrowserContext = self._authenticator.context
            
            self._library_scraper = LibraryScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            logger.info("Discovering flashcard sets...")
            
            # Get user's own sets
            all_sets: List[FlashCardSet] = self._library_scraper.get_user_sets()
            
            # Get shared sets
            shared_sets: List[FlashCardSet] = self._library_scraper.get_shared_sets()
            
            # Merge and deduplicate
            seen_ids: set[str] = {s.set_id for s in all_sets}
            for s in shared_sets:
                if s.set_id not in seen_ids:
                    all_sets.append(s)
                    seen_ids.add(s.set_id)
            
            # Save metadata
            metadata_path: str = self._save_metadata(all_sets)
            logger.info(f"Metadata saved to: {metadata_path}")
            
            return all_sets
            
        finally:
            self.close()
    
    def scrape_by_id(self, set_id: str) -> Optional[FlashCardSet]:
        """
        Scrape a single set by ID.
        
        Args:
            set_id: The set ID to scrape.
            
        Returns:
            FlashCardSet with cards, or None if not found.
        """
        # Find set in metadata
        set_info = self._find_set_in_metadata(set_id)
        
        if not set_info:
            logger.error(f"Set ID {set_id} not found in metadata")
            return None
        
        return self.scrape_by_url(set_info["url"])
    
    def scrape_by_url(self, url: str) -> Optional[FlashCardSet]:
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
            context: BrowserContext = self._authenticator.context
            
            self._set_scraper = SetScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            flash_set: FlashCardSet = self._set_scraper.scrape_set(url)
            
            # Export
            self._export_set(flash_set)
            
            return flash_set
            
        finally:
            self.close()
    
    def scrape_all(self) -> List[FlashCardSet]:
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
            context: BrowserContext = self._authenticator.context
            
            self._set_scraper = SetScraper(
                context=context,
                delay_min=self._config.get("scraper.delay_min", 2.0),
                delay_max=self._config.get("scraper.delay_max", 5.0),
                max_retries=self._config.get("scraper.max_retries", 3)
            )
            
            results: List[FlashCardSet] = []
            urls = [s["url"] for s in sets_info]
            
            for i, url in enumerate(urls, 1):
                logger.info(f"Scraping set {i}/{len(urls)}")
                try:
                    flash_set: FlashCardSet = self._set_scraper.scrape_set(url)
                    results.append(flash_set)
                    
                    # Export each set
                    self._export_set(flash_set)
                    
                except Exception as e:
                    logger.error(f"Failed to scrape {url}: {e}")
                    continue
            
            return results
            
        finally:
            self.close()
    
    def _export_set(self, flash_set: FlashCardSet) -> str:
        """Export a single set to Quizlet-compatible format."""
        output_dir = self._config.get("export.output_dir", "output")
        os.makedirs(output_dir, exist_ok=True)
        
        exporter = QuizletExporter()
        path: str = exporter.export(flash_set, output_dir)
        
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


def cmd_discover(args: argparse.Namespace, config: ConfigLoader) -> None:
    """Handle discover command."""
    scraper = QuizletScraper(config)
    
    sets: List[FlashCardSet] = scraper.discover(
        username=args.username,
        password=None  # Will prompt
    )
    
    print(f"\n✅ Discovered {len(sets)} flashcard sets!")
    print(f"📁 Metadata saved to: output/{QuizletScraper.METADATA_FILE}")
    print("\nSets found:")
    for _, s in enumerate(sets[:20], 1):
        print(f"  [{s.set_id}] {s.title} ({s.term_count} terms)")
    if len(sets) > 20:
        print(f"  ... and {len(sets) - 20} more")
    
    print("\n💡 Next steps:")
    print("  • Scrape one:  python -m src.main scrape --set-id <ID>")
    print("  • Scrape all:  python -m src.main scrape --all")


def cmd_scrape(args: argparse.Namespace, config: ConfigLoader) -> None:
    """Handle scrape command."""
    scraper = QuizletScraper(config)
    
    if args.all:
        # Scrape all
        results: List[FlashCardSet] = scraper.scrape_all()
        print(f"\n✅ Scraped {len(results)} sets!")
        
    elif args.set_id:
        # Scrape by ID
        result: FlashCardSet | None = scraper.scrape_by_id(args.set_id)
        if result:
            print(f"\n✅ Scraped: {result.title} ({len(result.cards)} cards)")
        else:
            print(f"\n❌ Set not found: {args.set_id}")
            sys.exit(1)
            
    elif args.url:
        # Scrape by URL
        result: FlashCardSet | None = scraper.scrape_by_url(args.url)
        if result:
            print(f"\n✅ Scraped: {result.title} ({len(result.cards)} cards)")
        else:
            print(f"\n❌ Failed to scrape: {args.url}")
            sys.exit(1)
    else:
        print("❌ Please specify --set-id, --url, or --all")
        sys.exit(1)


def cmd_logout(args: argparse.Namespace, config: ConfigLoader) -> None:
    """Handle logout command."""
    _ = args  # Unused
    scraper = QuizletScraper(config)
    scraper.logout()
    print("✅ Session cleared. Run 'discover' to login again.")


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Quizlet Private Flashcard Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main discover                    # Login and scan library
  python -m src.main scrape --set-id 123456      # Scrape specific set
  python -m src.main scrape --url "https://..."  # Scrape by URL
  python -m src.main scrape --all                # Scrape all discovered sets
  python -m src.main logout                      # Clear session
        """
    )
    
    parser.add_argument(
        "-c", "--config",
        default="config.yaml",
        help="Path to configuration file"
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
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Discover command
    discover_parser = subparsers.add_parser(
        "discover",
        help="Login and discover flashcard sets"
    )
    discover_parser.add_argument(
        "-u", "--username",
        help="Quizlet username or email"
    )
    
    # Scrape command
    scrape_parser = subparsers.add_parser(
        "scrape",
        help="Scrape flashcard content"
    )
    scrape_group = scrape_parser.add_mutually_exclusive_group()
    scrape_group.add_argument(
        "--set-id",
        help="Set ID to scrape (from metadata)"
    )
    scrape_group.add_argument(
        "--url",
        help="Direct URL to scrape"
    )
    scrape_group.add_argument(
        "--all",
        action="store_true",
        help="Scrape all sets from metadata"
    )
    
    # Logout command
    subparsers.add_parser(
        "logout",
        help="Clear saved session"
    )
    
    args: argparse.Namespace = parser.parse_args()
    
    # Setup logging
    log_level: int = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    
    # Load config
    config = ConfigLoader(args.config)
    
    # Override config with CLI args
    if args.headless:
        config.set("browser.headless", True)
    
    # Handle commands
    try:
        if args.command == "discover":
            cmd_discover(args, config)
        elif args.command == "scrape":
            cmd_scrape(args, config)
        elif args.command == "logout":
            cmd_logout(args, config)
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except SessionNotFoundError:
        print("\n❌ No session found. Run 'discover' first.")
        sys.exit(1)
    except SessionExpiredError:
        print("\n❌ Session expired. Run 'discover' to login again.")
        sys.exit(1)
    except AuthenticationError as e:
        print(f"\n❌ Authentication failed: {e}")
        sys.exit(1)
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception("An error occurred")
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
