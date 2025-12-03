"""
Quizlet Private Flashcard Scraper
=================================
Đơn giản, hiệu quả, tuân theo SOLID principle.

Flow:
  Phase 1: Login lấy session (chỉ cần 1 lần)
  Phase 2: Dùng session truy cập link set → parse flashcards

Usage:
  python main.py login     # Phase 1: Login lấy session
  python main.py scrape    # Phase 2: Scrape flashcards từ URL trong .env
"""
import os
import sys
import json
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass

from dotenv import load_dotenv
from patchright.sync_api import sync_playwright
from bs4 import BeautifulSoup


# =============================================================================
# Config (Single Responsibility)
# =============================================================================
@dataclass
class Config:
    """Load configuration từ .env"""
    email: str
    password: str
    set_url: str
    browser_data: Path = Path("browser_data")
    output_dir: Path = Path("output")
    
    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        return cls(
            email=os.getenv("QUIZLET_EMAIL", ""),
            password=os.getenv("QUIZLET_PASSWORD", ""),
            set_url=os.getenv("QUIZLET_SET_URL", ""),
        )


# =============================================================================
# Browser (Single Responsibility)
# =============================================================================
class Browser:
    """Quản lý Patchright browser với persistent session."""
    
    def __init__(self, config: Config, headless: bool = True):
        self._config = config
        self._headless = headless
        self._playwright = None
        self._context = None
        self._page = None
    
    def __enter__(self):
        self._playwright = sync_playwright().start()
        self._context = self._playwright.chromium.launch_persistent_context(
            user_data_dir=str(self._config.browser_data),
            channel="chrome",
            headless=self._headless,
            no_viewport=True
        )
        self._page = self._context.pages[0] if self._context.pages else self._context.new_page()
        return self
    
    def __exit__(self, *args):
        if self._context:
            self._context.close()
        if self._playwright:
            self._playwright.stop()
    
    @property
    def page(self):
        return self._page
    
    def goto(self, url: str):
        self._page.goto(url)
        self._page.wait_for_timeout(2000)
    
    def get_html(self) -> str:
        return self._page.content()


# =============================================================================
# Auth (Single Responsibility)
# =============================================================================
class QuizletAuth:
    """Handle Quizlet login."""
    
    LOGIN_URL = "https://quizlet.com/login"
    
    def __init__(self, browser: Browser, config: Config):
        self._browser = browser
        self._config = config
    
    def login(self) -> bool:
        """Login và lưu session."""
        print(f"🔐 Logging in as {self._config.email}...")
        
        self._browser.goto(self.LOGIN_URL)
        page = self._browser.page
        
        # Fill form
        page.fill('input[name="username"]', self._config.email)
        page.fill('input[name="password"]', self._config.password)
        page.click('button[type="submit"]')
        
        # Wait for redirect
        page.wait_for_timeout(5000)
        
        # Check login success
        if "login" not in page.url.lower():
            print("✅ Login thành công! Session đã được lưu.")
            return True
        else:
            print("❌ Login thất bại!")
            return False


# =============================================================================
# Parser (Single Responsibility) 
# =============================================================================
class FlashcardParser:
    """Parse flashcards từ HTML."""
    
    def parse(self, html: str) -> list[dict]:
        """
        Parse HTML để lấy các cặp thuật ngữ + định nghĩa.
        
        Structure:
          div.SetPageTermsList-term
            └── div[data-testid="set-page-term-card-side"] (thuật ngữ - câu hỏi + đáp án)
            └── div[data-testid="set-page-term-card-side"] (định nghĩa - đáp án đúng)
        """
        soup = BeautifulSoup(html, 'html.parser')
        flashcards = []
        
        # Tìm tất cả card
        cards = soup.select('div.SetPageTermsList-term')
        print(f"📝 Found {len(cards)} cards")
        
        for card in cards:
            sides = card.select('div[data-testid="set-page-term-card-side"]')
            
            if len(sides) >= 2:
                # Side 1: Thuật ngữ (câu hỏi + các đáp án A,B,C,D)
                term_el = sides[0].select_one('span.TermText')
                # Side 2: Định nghĩa (đáp án đúng)
                definition_el = sides[1].select_one('span.TermText')
                
                if term_el and definition_el:
                    # Lấy text, giữ format xuống hàng
                    term = self._extract_text(term_el)
                    definition = definition_el.get_text(strip=True)
                    
                    flashcards.append({
                        "term": term,
                        "definition": definition
                    })
        
        return flashcards
    
    def _extract_text(self, element) -> str:
        """Extract text từ element, convert <p> thành newline."""
        parts = []
        for p in element.find_all('p'):
            text = p.get_text(strip=True)
            if text:
                parts.append(text)
        
        if parts:
            return '\n'.join(parts)
        
        return element.get_text(strip=True)


# =============================================================================
# Exporter
# =============================================================================
class TxtExporter:
    """Export với format [ch] câu hỏi [da] đáp án."""
    
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir
    
    def export(self, flashcards: list[dict], filename: str = "flashcards.txt") -> str:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / filename
        
        with open(path, "w", encoding="utf-8") as f:
            for i, card in enumerate(flashcards):
                if i > 0:
                    f.write("[ch]\n")  # Separator giữa các card
                f.write(f"{card['term']}\n")
                f.write(f"[da]{card['definition']}\n")
        
        return str(path)


# =============================================================================
# Scraper (Orchestration)
# =============================================================================
class QuizletScraper:
    """Scrape flashcards từ Quizlet set URL."""
    
    def __init__(self, browser: Browser, parser: FlashcardParser):
        self._browser = browser
        self._parser = parser
    
    def scrape(self, url: str) -> list[dict]:
        """Truy cập URL và parse flashcards."""
        print(f"🎯 Scraping: {url[:60]}...")
        
        self._browser.goto(url)
        self._browser.page.wait_for_timeout(3000)  # Đợi load content
        
        html = self._browser.get_html()
        flashcards = self._parser.parse(html)
        
        return flashcards


# =============================================================================
# CLI
# =============================================================================
def cmd_login(config: Config):
    """Phase 1: Login lấy session (headless=False để thấy captcha nếu có)."""
    with Browser(config, headless=False) as browser:
        auth = QuizletAuth(browser, config)
        auth.login()


def cmd_scrape(config: Config):
    """Phase 2: Scrape flashcards (cần headless=False để bypass Cloudflare)."""
    if not config.set_url:
        print("❌ Chưa có QUIZLET_SET_URL trong .env!")
        return
    
    with Browser(config, headless=False) as browser:
        parser = FlashcardParser()
        scraper = QuizletScraper(browser, parser)
        
        flashcards = scraper.scrape(config.set_url)
        
        if flashcards:
            # Export
            exporter = TxtExporter(config.output_dir)
            output_path = exporter.export(flashcards)
            
            print(f"\n✅ Scraped {len(flashcards)} flashcards!")
            print(f"   📄 {output_path}")
        else:
            print("❌ Không tìm thấy flashcard nào!")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nCommands:")
        print("  python main.py login   - Login lấy session")
        print("  python main.py scrape  - Scrape flashcards")
        return
    
    config = Config.load()
    command = sys.argv[1].lower()
    
    if command == "login":
        cmd_login(config)
    elif command == "scrape":
        cmd_scrape(config)
    else:
        print(f"❌ Unknown command: {command}")


if __name__ == "__main__":
    main()
