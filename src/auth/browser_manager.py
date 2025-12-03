"""
Browser management module.
Following Single Responsibility Principle - only handles browser lifecycle.
Includes anti-detection measures for Cloudflare bypass.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright

if TYPE_CHECKING:
    pass

logger: logging.Logger = logging.getLogger(__name__)

# Realistic user agents pool
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
]


@dataclass
class BrowserConfig:
    """Browser configuration settings."""

    headless: bool = False
    slow_mo: int = 100
    timeout: int = 30000
    user_agent: str | None = None
    stealth: bool = True
    # Browser executable path (None = use bundled)
    executable_path: str | None = None
    # Extra launch args
    extra_args: list[str] = field(default_factory=list)


class BrowserManager:
    """
    Manages browser lifecycle and context creation.
    Single Responsibility: Browser resource management only.
    Includes anti-detection measures for Cloudflare bypass.
    """

    def __init__(self, config: BrowserConfig) -> None:
        self._config = config
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def start(self) -> None:
        """Start the browser with anti-detection settings."""
        if self._browser is not None:
            logger.warning("Browser already started")
            return

        logger.info("Starting browser...")
        self._playwright = sync_playwright().start()

        # Anti-detection launch args
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-web-security",
            "--disable-features=IsolateOrigins,site-per-process",
            "--allow-running-insecure-content",
            "--start-maximized",
            *self._config.extra_args,
        ]

        # Use Firefox for better Cloudflare bypass
        self._browser = self._playwright.firefox.launch(
            headless=self._config.headless,
            slow_mo=self._config.slow_mo,
            args=launch_args if self._config.executable_path else None,
            executable_path=self._config.executable_path,
        )
        logger.info(f"Browser started (headless={self._config.headless}, type=firefox)")

    def create_context(self, storage_state: str | None = None) -> BrowserContext:
        """
        Create a new browser context with anti-detection measures.

        Args:
            storage_state: Path to session file for authentication state.

        Returns:
            BrowserContext instance.
        """
        if self._browser is None:
            self.start()

        assert self._browser is not None  # For type checker

        # Random user agent for each context
        user_agent = self._config.user_agent or random.choice(USER_AGENTS)

        # Context options with realistic browser fingerprint
        context_options: dict[str, object] = {
            "viewport": None,  # None = use full window size (maximized)
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "color_scheme": "light",
            "device_scale_factor": 1,
            "has_touch": False,
            "is_mobile": False,
            "java_script_enabled": True,
            # Firefox-specific: better fingerprint
            "ignore_https_errors": True,
        }

        if storage_state:
            context_options["storage_state"] = storage_state
            logger.info(f"Loading session from: {storage_state}")

        context = self._browser.new_context(**context_options)  # type: ignore[arg-type]

        # Apply stealth scripts
        if self._config.stealth:
            self._apply_stealth(context)

        context.set_default_timeout(self._config.timeout)

        return context

    def _apply_stealth(self, context: BrowserContext) -> None:
        """
        Apply stealth scripts to evade bot detection.

        Args:
            context: Browser context to apply stealth to.
        """
        stealth_js = """
        // Override webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });

        // Delete automation indicators
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;

        // Override plugins to look real
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ];
                plugins.item = (i) => plugins[i];
                plugins.namedItem = (name) => plugins.find(p => p.name === name);
                plugins.refresh = () => {};
                return plugins;
            }
        });

        // Override languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });

        // Make chrome object look real
        if (!window.chrome) {
            window.chrome = {
                runtime: {},
                loadTimes: function() {},
                csi: function() {},
                app: {}
            };
        }

        // Override permissions query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // Fake WebGL vendor
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';
            return getParameter.apply(this, arguments);
        };
        """
        context.add_init_script(stealth_js)
        logger.debug("Stealth scripts applied")

    def close(self) -> None:
        """Close the browser and cleanup resources."""
        if self._browser:
            logger.info("Closing browser...")
            self._browser.close()
            self._browser = None

        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def __enter__(self) -> BrowserManager:
        """Context manager entry."""
        self.start()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Context manager exit."""
        self.close()

    @property
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None
