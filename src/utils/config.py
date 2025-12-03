"""
Configuration loader with support for YAML and environment variables.
Following Single Responsibility Principle - only handles configuration.
"""

import os
import yaml
import logging
from typing import Any, Dict
from pathlib import Path

from src.core.exceptions import ConfigurationError

logger: logging.Logger = logging.getLogger(__name__)


class ConfigLoader:
    """
    Loads and manages configuration from YAML files and environment variables.
    Single Responsibility: Configuration management only.
    """
    
    def __init__(self, config_path: str = "config.yaml") -> None:
        """
        Initialize config loader.
        
        Args:
            config_path: Path to YAML configuration file.
        """
        self._config_path: str = config_path
        self._config: Dict[str, Any] = {}
        self._load()
    
    def _load(self) -> None:
        """Load configuration from file."""
        path = Path(self._config_path)
        
        if not path.exists():
            logger.warning(f"Config file not found: {self._config_path}, using defaults")
            self._config = self._get_defaults()
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f) or {}
            logger.info(f"Loaded configuration from: {self._config_path}")
        except yaml.YAMLError as e:
            raise ConfigurationError(f"Failed to parse config file: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load config file: {str(e)}")
        
        # Merge with defaults
        defaults: Dict[str, Any] = self._get_defaults()
        self._config = self._deep_merge(defaults, self._config)
        
        # Override with environment variables
        self._apply_env_overrides()
    
    def _get_defaults(self) -> Dict[str, Any]:
        """Get default configuration values."""
        return {
            "quizlet": {
                "base_url": "https://quizlet.com",
                "login_url": "https://quizlet.com/login",
                "library_url": "https://quizlet.com/latest"
            },
            "browser": {
                "headless": False,
                "slow_mo": 100,
                "timeout": 30000
            },
            "scraper": {
                "delay_min": 2.0,
                "delay_max": 5.0,
                "max_retries": 3
            },
            "export": {
                "output_dir": "output",
                "formats": ["json"],
                "include_images": False
            },
            "auth": {
                "session_dir": "auth",
                "session_file": "quizlet_session.json"
            }
        }
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result: Dict[str, Any] = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides."""
        # Map of env vars to config paths
        env_mapping: Dict[str, Optional[str]] = {
            "QUIZLET_USERNAME": None,  # Special handling
            "QUIZLET_PASSWORD": None,  # Special handling
            "QUIZLET_HEADLESS": "browser.headless",
            "QUIZLET_OUTPUT_DIR": "export.output_dir",
        }
        
        for env_var, config_path in env_mapping.items():
            value = os.environ.get(env_var)
            if value and config_path:
                self._set_nested(config_path, value)
    
    def _set_nested(self, path: str, value: Any) -> None:
        """Set a nested configuration value using dot notation."""
        keys: list[str] = path.split(".")
        current: Dict[str, Any] = self._config
        
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Type conversion
        if isinstance(value, str):
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            else:
                try:
                    value = float(value)
                except ValueError:
                    pass
        
        current[keys[-1]] = value
    
    def set(self, key: str, value: Any) -> None:
        """
        Set a configuration value by key (supports dot notation).
        
        Args:
            key: Configuration key (e.g., "browser.headless").
            value: Value to set.
        """
        self._set_nested(key, value)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key (supports dot notation).
        
        Args:
            key: Configuration key (e.g., "browser.headless").
            default: Default value if key not found.
            
        Returns:
            Configuration value.
        """
        keys: list[str] = key.split(".")
        current: Any = self._config
        
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        
        return current
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get an entire configuration section.
        
        Args:
            section: Section name (e.g., "browser").
            
        Returns:
            Configuration dictionary for the section.
        """
        return self.get(section, {})
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load()
        logger.info("Configuration reloaded")
    
    @property
    def session_path(self) -> str:
        """Get full path to session file."""
        session_dir = str(self.get("auth.session_dir", "auth"))
        session_file = str(self.get("auth.session_file", "quizlet_session.json"))
        return os.path.join(session_dir, session_file)
