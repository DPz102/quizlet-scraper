"""
Custom exceptions for the Quizlet scraper.
Following Single Responsibility Principle - dedicated exception handling.
"""


class QuizletScraperError(Exception):
    """Base exception for all scraper errors."""
    pass


class AuthenticationError(QuizletScraperError):
    """Raised when authentication fails."""
    pass


class SessionExpiredError(AuthenticationError):
    """Raised when the session has expired."""
    pass


class SessionNotFoundError(AuthenticationError):
    """Raised when session file is not found."""
    pass


class ScrapingError(QuizletScraperError):
    """Raised when scraping fails."""
    pass


class SetNotFoundError(ScrapingError):
    """Raised when a flashcard set is not found."""
    pass


class AccessDeniedError(ScrapingError):
    """Raised when access to a resource is denied."""
    pass


class RateLimitError(ScrapingError):
    """Raised when rate limit is hit."""
    pass


class ExportError(QuizletScraperError):
    """Raised when export fails."""
    pass


class ConfigurationError(QuizletScraperError):
    """Raised when configuration is invalid."""
    pass
