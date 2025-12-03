"""
Quizlet Authenticator implementation.
Following Single Responsibility Principle - only handles authentication.
"""

import os
import logging
from typing import Optional
from playwright.sync_api import BrowserContext, Page, Locator, TimeoutError as PlaywrightTimeout

from src.core.exceptions import (
    AuthenticationError,
    SessionExpiredError,
    SessionNotFoundError
)

logger: logging.Logger = logging.getLogger(__name__)


class QuizletAuthenticator:
    """
    Handles Quizlet authentication.
    Single Responsibility: Authentication and session management only.
    """
    
    QUIZLET_LOGIN_URL = "https://quizlet.com/login"
    QUIZLET_HOME_URL = "https://quizlet.com"
    QUIZLET_LATEST_URL = "https://quizlet.com/latest"
    
    def __init__(self, context: BrowserContext) -> None:
        """
        Initialize authenticator with browser context.
        
        Args:
            context: Playwright browser context to use.
        """
        self._context: BrowserContext = context
        self._page: Optional[Page] = None
    
    @property
    def context(self) -> BrowserContext:
        """Get the browser context."""
        return self._context
    
    def _get_page(self) -> Page:
        """Get or create a page."""
        if self._page is None or self._page.is_closed():
            self._page = self._context.new_page()
        return self._page
    
    def login(self, username: str, password: str) -> bool:
        """
        Perform login to Quizlet.
        
        Args:
            username: Quizlet username or email.
            password: Quizlet password.
            
        Returns:
            True if login successful.
            
        Raises:
            AuthenticationError: If login fails.
        """
        page: Page = self._get_page()
        
        try:
            logger.info("Navigating to Quizlet login page...")
            page.goto(self.QUIZLET_LOGIN_URL, wait_until="networkidle")
            
            # Wait for login form
            page.wait_for_selector('input[type="text"], input[type="email"]', timeout=10000)
            
            logger.info("Filling login credentials...")
            
            # Fill username/email
            username_input: Locator = page.locator('input[type="text"], input[type="email"]').first
            username_input.fill(username)
            
            # Fill password
            password_input: Locator = page.locator('input[type="password"]')
            password_input.fill(password)
            
            # Click login button
            login_button: Locator = page.locator('button[type="submit"]')
            login_button.click()
            
            # Wait for navigation after login
            logger.info("Waiting for login to complete...")
            
            # Check for successful redirect or error
            try:
                # Wait for redirect to home or latest
                page.wait_for_url(
                    lambda url: "/login" not in url,
                    timeout=30000
                )
                
                # Verify we're logged in by checking for user-specific elements
                if self.is_authenticated():
                    logger.info("Login successful!")
                    return True
                else:
                    raise AuthenticationError("Login appeared to succeed but authentication check failed")
                    
            except PlaywrightTimeout:
                # Check for error messages
                error_elem: Locator = page.locator('[class*="error"], [class*="Error"]').first
                if error_elem.is_visible():
                    error_text: str = error_elem.inner_text()
                    raise AuthenticationError(f"Login failed: {error_text}")
                raise AuthenticationError("Login timed out")
                
        except PlaywrightTimeout as e:
            raise AuthenticationError(f"Login timeout: {str(e)}")
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Login failed: {str(e)}")
    
    def is_authenticated(self) -> bool:
        """
        Check if current session is authenticated.
        
        Returns:
            True if user is logged in.
        """
        page: Page = self._get_page()
        
        try:
            # Navigate to a page that requires auth if not already there
            current_url: str = page.url
            if not current_url or current_url == "about:blank":
                page.goto(self.QUIZLET_LATEST_URL, wait_until="networkidle")
            
            # Check for login redirect (means not authenticated)
            if "/login" in page.url:
                return False
            
            # Check for user menu/avatar (indicates logged in)
            # Quizlet shows user avatar when logged in
            user_indicators: list[str] = [
                '[data-testid="user-menu"]',
                '[class*="UserAvatar"]',
                '[class*="ProfileIcon"]',
                'button[aria-label*="profile"]',
                '[class*="NavigationUser"]'
            ]
            
            for selector in user_indicators:
                try:
                    if page.locator(selector).first.is_visible(timeout=2000):
                        return True
                except:
                    continue
            
            # Fallback: check if we can access /latest without redirect
            if "/latest" in page.url or "/home" in page.url:
                return True
                
            return False
            
        except Exception as e:
            logger.warning(f"Auth check failed: {str(e)}")
            return False
    
    def save_session(self, path: str) -> None:
        """
        Save current session to file.
        
        Args:
            path: Path to save session file.
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        
        # Save storage state (cookies, localStorage, etc.)
        self._context.storage_state(path=path)
        logger.info(f"Session saved to: {path}")
    
    def load_session(self, path: str) -> bool:
        """
        Check if session file exists and is valid.
        Note: Session loading is done at context creation time.
        
        Args:
            path: Path to session file.
            
        Returns:
            True if session file exists.
        """
        if not os.path.exists(path):
            raise SessionNotFoundError(f"Session file not found: {path}")
        
        # Verify session is still valid by checking authentication
        if not self.is_authenticated():
            raise SessionExpiredError("Session has expired")
        
        return True
    
    def logout(self) -> None:
        """Log out from Quizlet."""
        page: Page = self._get_page()
        
        try:
            # Navigate to logout URL
            page.goto(f"{self.QUIZLET_HOME_URL}/logout", wait_until="networkidle")
            logger.info("Logged out successfully")
        except Exception as e:
            logger.warning(f"Logout failed: {str(e)}")
    
    def close(self) -> None:
        """Close the page."""
        if self._page and not self._page.is_closed():
            self._page.close()
            self._page = None
    
    def manual_login(self, timeout: int = 300) -> bool:
        """
        Open browser for manual login (supports Google OAuth, etc.).
        
        User will manually complete the login process in the browser.
        Session is saved once login is detected.
        
        Args:
            timeout: Maximum time to wait for login in seconds.
            
        Returns:
            True if login successful.
            
        Raises:
            AuthenticationError: If login times out or fails.
        """
        page: Page = self._get_page()
        
        try:
            logger.info("Opening Quizlet login page for manual login...")
            logger.info("Please complete the login in the browser window.")
            logger.info(f"Waiting up to {timeout} seconds for login...")
            
            # Maximize window for better UX
            page.set_viewport_size({"width": 1920, "height": 1080})
            
            page.goto(self.QUIZLET_LOGIN_URL, wait_until="networkidle")
            
            # Wait for user to complete login (redirect away from /login)
            try:
                page.wait_for_url(
                    lambda url: "/login" not in url and "quizlet.com" in url,
                    timeout=timeout * 1000  # Convert to ms
                )
            except PlaywrightTimeout:
                raise AuthenticationError(
                    f"Login timed out after {timeout} seconds. "
                    "Please try again and complete login faster."
                )
            
            # Give a moment for session to settle
            page.wait_for_load_state("networkidle")
            
            # Verify authentication
            if self.is_authenticated():
                logger.info("Manual login successful!")
                return True
            else:
                raise AuthenticationError(
                    "Login appeared to complete but authentication check failed"
                )
                
        except PlaywrightTimeout as e:
            raise AuthenticationError(f"Manual login timeout: {e!s}")
        except Exception as e:
            if isinstance(e, AuthenticationError):
                raise
            raise AuthenticationError(f"Manual login failed: {e!s}")
