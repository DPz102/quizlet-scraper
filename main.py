"""Quizlet Flashcard Scraper"""
import os
import sys
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv
from patchright.sync_api import sync_playwright
from bs4 import BeautifulSoup


@dataclass
class Config:
    email: str
    password: str
    set_urls: list[str]
    browser_data: Path = Path("browser_data")
    output_dir: Path = Path("output")

    @classmethod
    def load(cls) -> "Config":
        load_dotenv()
        urls_raw = os.getenv("QUIZLET_SET_URLS", "")
        urls = [u.strip() for u in urls_raw.replace("\n", ",").split(",") if u.strip()]
        return cls(
            email=os.getenv("QUIZLET_EMAIL", ""),
            password=os.getenv("QUIZLET_PASSWORD", ""),
            set_urls=urls,
        )


class Browser:
    def __init__(self, config: Config, headless: bool = False):
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


class QuizletAuth:
    LOGIN_URL = "https://quizlet.com/login"

    def __init__(self, browser: Browser, config: Config):
        self._browser = browser
        self._config = config

    def _accept_cookies(self):
        page = self._browser.page
        try:
            accept_btn = page.locator('button:has-text("Accept All")').first
            if accept_btn.is_visible(timeout=3000):
                accept_btn.click()
                print("🍪 Accepted cookies")
                page.wait_for_timeout(1000)
        except:
            pass

    def login_auto(self) -> bool:
        print(f"🔐 Auto login as {self._config.email}...")
        self._browser.goto(self.LOGIN_URL)
        self._accept_cookies()

        page = self._browser.page
        page.fill('input[name="username"]', self._config.email)
        page.fill('input[name="password"]', self._config.password)
        page.click('button[type="submit"]')
        page.wait_for_timeout(5000)

        if "login" not in page.url.lower():
            print("✅ Login thành công!")
            return True
        else:
            print("❌ Login thất bại!")
            return False

    def login_manual(self) -> bool:
        print("🔐 Manual login - Hãy đăng nhập thủ công (Google/Facebook)...")
        self._browser.goto(self.LOGIN_URL)
        self._accept_cookies()

        page = self._browser.page
        print("⏳ Đang đợi bạn login... (tự động detect)")

        # Poll check mỗi 2 giây, timeout 3 phút
        for _ in range(90):
            page.wait_for_timeout(2000)
            try:
                # Check 1: Avatar/profile element (chỉ hiện khi logged in)
                if page.locator('[data-testid="user-avatar"], .SiteHeader-userAvatar, img[alt*="avatar"]').first.is_visible(timeout=500):
                    print("✅ Login thành công!")
                    return True
                
                # Check 2: URL đã ở trang chính Quizlet (không phải login/google)
                url = page.url.lower()
                if "quizlet.com" in url and "/login" not in url and "accounts.google" not in url and "facebook.com" not in url:
                    # Double check bằng cách tìm element login-only
                    if page.locator('a[href="/settings"], button[aria-label*="account"]').first.is_visible(timeout=500):
                        print("✅ Login thành công!")
                        return True
            except:
                pass

        print("❌ Timeout sau 3 phút")
        return False


class FlashcardParser:
    def parse(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, 'html.parser')
        flashcards = []
        cards = soup.select('div.SetPageTermsList-term')
        print(f"📝 Found {len(cards)} cards")

        for card in cards:
            sides = card.select('div[data-testid="set-page-term-card-side"]')
            if len(sides) >= 2:
                term_el = sides[0].select_one('span.TermText')
                definition_el = sides[1].select_one('span.TermText')
                if term_el and definition_el:
                    term = self._extract_text(term_el)
                    definition = definition_el.get_text(strip=True)
                    flashcards.append({"term": term, "definition": definition})
        return flashcards

    def _extract_text(self, element) -> str:
        parts = [p.get_text(strip=True) for p in element.find_all('p') if p.get_text(strip=True)]
        return '\n'.join(parts) if parts else element.get_text(strip=True)


class TxtExporter:
    def __init__(self, output_dir: Path):
        self._output_dir = output_dir

    def export(self, flashcards: list[dict], filename: str = "flashcards.txt") -> str:
        self._output_dir.mkdir(parents=True, exist_ok=True)
        path = self._output_dir / filename
        with open(path, "w", encoding="utf-8") as f:
            for i, card in enumerate(flashcards):
                if i > 0:
                    f.write("[ch]\n")
                f.write(f"{card['term']}\n")
                f.write(f"[da]{card['definition']}\n")
        return str(path)


class QuizletScraper:
    def __init__(self, browser: Browser, parser: FlashcardParser):
        self._browser = browser
        self._parser = parser

    def scrape(self, url: str) -> list[dict]:
        print(f"🎯 Scraping: {url[:60]}...")
        self._browser.goto(url)
        self._browser.page.wait_for_timeout(3000)
        return self._parser.parse(self._browser.get_html())


def cmd_login(config: Config, mode: str):
    with Browser(config) as browser:
        auth = QuizletAuth(browser, config)
        success = auth.login_auto() if mode == "auto" else auth.login_manual()
        
        if not success:
            # Xóa browser_data nếu login thất bại
            import shutil
            if config.browser_data.exists():
                shutil.rmtree(config.browser_data)
                print("🗑️ Đã xóa session data do login thất bại")


def cmd_scrape(config: Config):
    if not config.set_urls:
        print("❌ Chưa có QUIZLET_SET_URLS trong .env!")
        return

    print(f"📚 Found {len(config.set_urls)} URL(s)")

    with Browser(config) as browser:
        scraper = QuizletScraper(browser, FlashcardParser())
        exporter = TxtExporter(config.output_dir)

        for i, url in enumerate(config.set_urls, 1):
            print(f"\n[{i}/{len(config.set_urls)}] {url[:50]}...")
            flashcards = scraper.scrape(url)
            if flashcards:
                slug = url.rstrip("/").split("/")[-1][:30] or f"set_{i}"
                output_path = exporter.export(flashcards, f"{slug}.txt")
                print(f"   ✅ {len(flashcards)} cards → {output_path}")
            else:
                print("   ❌ Không tìm thấy flashcard!")


def main():
    if len(sys.argv) < 2:
        print("Quizlet Flashcard Scraper\n")
        print("  python main.py login auto    Login với email/password")
        print("  python main.py login manual  Login thủ công (Google/Facebook)")
        print("  python main.py scrape        Scrape flashcards từ URLs trong .env")
        return

    config = Config.load()
    cmd = sys.argv[1].lower()

    if cmd == "login":
        mode = sys.argv[2].lower() if len(sys.argv) > 2 else "auto"
        if mode not in ["auto", "manual"]:
            print("❌ Mode phải là 'auto' hoặc 'manual'")
            return
        cmd_login(config, mode)
    elif cmd == "scrape":
        cmd_scrape(config)
    else:
        print(f"❌ Unknown command: {cmd}")


if __name__ == "__main__":
    main()
