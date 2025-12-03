"""
Base command interface following Interface Segregation Principle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
import argparse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.utils.config import ConfigLoader


class BaseCommand(ABC):
    """Abstract base class for CLI commands."""
    
    def __init__(self, config: ConfigLoader) -> None:
        """
        Initialize command with configuration.
        
        Args:
            config: Configuration loader instance.
        """
        self._config = config
    
    @abstractmethod
    def execute(self, args: argparse.Namespace) -> int:
        """
        Execute the command.
        
        Args:
            args: Parsed command line arguments.
            
        Returns:
            Exit code (0 for success, non-zero for failure).
        """
        ...
    
    @staticmethod
    @abstractmethod
    def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
        """
        Register command with argument parser.
        
        Args:
            subparsers: Subparsers action to add command to.
        """
        ...
