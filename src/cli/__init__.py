"""
CLI module for Quizlet Scraper.
Contains command handlers following Single Responsibility Principle.
"""

from src.cli.commands import DiscoverCommand, ScrapeCommand, LogoutCommand, LoginCommand

__all__ = ["DiscoverCommand", "ScrapeCommand", "LogoutCommand", "LoginCommand"]
