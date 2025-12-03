"""
CLI command implementations.
Each command follows Single Responsibility Principle.
"""

from __future__ import annotations

import argparse
import logging
import sys
from getpass import getpass
from typing import TYPE_CHECKING

from src.cli.base import BaseCommand
from src.core.interfaces import FlashCardSet
from src.services.scraper_service import ScraperService

if TYPE_CHECKING:
    from src.utils.config import ConfigLoader

logger: logging.Logger = logging.getLogger(__name__)


class LoginCommand(BaseCommand):
    """
    Handle manual login command.
    Opens browser for user to login manually (supports Google OAuth).
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute manual login flow."""
        service = ScraperService(self._config)
        
        try:
            timeout = args.timeout if hasattr(args, "timeout") else 300
            success = service.manual_login(timeout=timeout)
            
            if success:
                print("\n✅ Login successful! Session saved.")
                print("💡 You can now run: python -m src.main discover")
                return 0
            else:
                print("\n❌ Login failed or timed out.")
                return 1
        finally:
            service.close()
    
    @staticmethod
    def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Register login command."""
        parser = subparsers.add_parser(
            "login",
            help="Open browser for manual login (supports Google OAuth)"
        )
        parser.add_argument(
            "-t", "--timeout",
            type=int,
            default=300,
            help="Timeout in seconds to wait for login (default: 300)"
        )


class DiscoverCommand(BaseCommand):
    """
    Handle discover command.
    Discovers all flashcard sets in user's library.
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute discover flow."""
        service = ScraperService(self._config)
        
        try:
            # Determine login method
            manual = getattr(args, "manual", False)
            username = getattr(args, "username", None)
            
            sets = service.discover(
                username=username,
                manual_login=manual
            )
            
            self._print_results(sets)
            return 0
            
        except KeyboardInterrupt:
            print("\n\n⚠️ Interrupted by user")
            return 1
        finally:
            service.close()
    
    def _print_results(self, sets: list[FlashCardSet]) -> None:
        """Print discovery results."""
        print(f"\n✅ Discovered {len(sets)} flashcard sets!")
        print(f"📁 Metadata saved to: output/sets_metadata.json")
        print("\nSets found:")
        
        for s in sets[:20]:
            print(f"  [{s.set_id}] {s.title} ({s.term_count} terms)")
        
        if len(sets) > 20:
            print(f"  ... and {len(sets) - 20} more")
        
        print("\n💡 Next steps:")
        print("  • Scrape one:  python -m src.main scrape --set-id <ID>")
        print("  • Scrape all:  python -m src.main scrape --all")
    
    @staticmethod
    def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Register discover command."""
        parser = subparsers.add_parser(
            "discover",
            help="Login and discover flashcard sets"
        )
        parser.add_argument(
            "-u", "--username",
            help="Quizlet username or email"
        )
        parser.add_argument(
            "-m", "--manual",
            action="store_true",
            help="Use manual login (opens browser for Google OAuth, etc.)"
        )


class ScrapeCommand(BaseCommand):
    """
    Handle scrape command.
    Scrapes flashcard content from sets.
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute scrape flow."""
        service = ScraperService(self._config)
        
        try:
            if args.all:
                return self._scrape_all(service)
            elif args.set_id:
                return self._scrape_by_id(service, args.set_id)
            elif args.url:
                return self._scrape_by_url(service, args.url)
            else:
                print("❌ Please specify --set-id, --url, or --all")
                return 1
        finally:
            service.close()
    
    def _scrape_all(self, service: ScraperService) -> int:
        """Scrape all sets from metadata."""
        results = service.scrape_all()
        print(f"\n✅ Scraped {len(results)} sets!")
        return 0
    
    def _scrape_by_id(self, service: ScraperService, set_id: str) -> int:
        """Scrape single set by ID."""
        result = service.scrape_by_id(set_id)
        if result:
            print(f"\n✅ Scraped: {result.title} ({len(result.cards)} cards)")
            return 0
        else:
            print(f"\n❌ Set not found: {set_id}")
            return 1
    
    def _scrape_by_url(self, service: ScraperService, url: str) -> int:
        """Scrape single set by URL."""
        result = service.scrape_by_url(url)
        if result:
            print(f"\n✅ Scraped: {result.title} ({len(result.cards)} cards)")
            return 0
        else:
            print(f"\n❌ Failed to scrape: {url}")
            return 1
    
    @staticmethod
    def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Register scrape command."""
        parser = subparsers.add_parser(
            "scrape",
            help="Scrape flashcard content"
        )
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            "--set-id",
            help="Set ID to scrape (from metadata)"
        )
        group.add_argument(
            "--url",
            help="Direct URL to scrape"
        )
        group.add_argument(
            "--all",
            action="store_true",
            help="Scrape all sets from metadata"
        )


class LogoutCommand(BaseCommand):
    """
    Handle logout command.
    Clears saved session.
    """
    
    def execute(self, args: argparse.Namespace) -> int:
        """Execute logout flow."""
        _ = args  # Unused
        service = ScraperService(self._config)
        service.logout()
        print("✅ Session cleared. Run 'login' or 'discover' to login again.")
        return 0
    
    @staticmethod
    def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """Register logout command."""
        subparsers.add_parser(
            "logout",
            help="Clear saved session"
        )
