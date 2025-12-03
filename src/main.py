"""
Quizlet Scraper - Main Entry Point.
Thin entry point following Single Responsibility Principle.
All business logic is in services/, CLI handling in cli/.

Commands:
    login     - Open browser for manual login (Google OAuth supported)
    discover  - Scan library and save metadata
    scrape    - Scrape specific set(s) using saved session
    logout    - Clear saved session
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import TYPE_CHECKING

from src.cli.commands import DiscoverCommand, LoginCommand, LogoutCommand, ScrapeCommand
from src.core.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    SessionNotFoundError,
)
from src.utils.config import ConfigLoader
from src.utils.logging_config import setup_logging

if TYPE_CHECKING:
    from src.cli.base import BaseCommand

logger: logging.Logger = logging.getLogger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure argument parser."""
    parser = argparse.ArgumentParser(
        description="Quizlet Private Flashcard Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main login                       # Manual login (Google OAuth)
  python -m src.main discover                    # Login and scan library
  python -m src.main discover -m                 # Discover with manual login
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
    
    return parser


def register_commands(parser: argparse.ArgumentParser) -> None:
    """Register all CLI commands."""
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Register each command
    LoginCommand.register(subparsers)
    DiscoverCommand.register(subparsers)
    ScrapeCommand.register(subparsers)
    LogoutCommand.register(subparsers)


def get_command(command_name: str, config: ConfigLoader) -> BaseCommand | None:
    """
    Get command instance by name.
    
    Args:
        command_name: Name of the command.
        config: Configuration loader.
        
    Returns:
        Command instance or None if not found.
    """
    commands: dict[str, type[BaseCommand]] = {
        "login": LoginCommand,
        "discover": DiscoverCommand,
        "scrape": ScrapeCommand,
        "logout": LogoutCommand,
    }
    
    command_class = commands.get(command_name)
    if command_class:
        return command_class(config)
    return None


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    register_commands(parser)
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    setup_logging(level=log_level)
    
    # Load config
    config = ConfigLoader(args.config)
    
    # Override config with CLI args
    if args.headless:
        config.set("browser.headless", True)
    
    # Handle commands
    if not args.command:
        parser.print_help()
        return
    
    try:
        command = get_command(args.command, config)
        if command:
            exit_code = command.execute(args)
            sys.exit(exit_code)
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        print("\n\n⚠️ Interrupted by user")
        sys.exit(1)
    except SessionNotFoundError:
        print("\n❌ No session found. Run 'login' or 'discover' first.")
        sys.exit(1)
    except SessionExpiredError:
        print("\n❌ Session expired. Run 'login' or 'discover -m' to login again.")
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
