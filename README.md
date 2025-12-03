# Quizlet Private Flashcard Scraper

Export flashcards từ Quizlet, bao gồm cả private sets được chia sẻ với bạn.

## Features

- 🔐 Đăng nhập và lưu session để tái sử dụng
- 📚 Tự động phát hiện tất cả flashcard sets trong thư viện
- 🔗 Hỗ trợ private sets được share qua classes/folders
- 📤 Export ra nhiều định dạng: JSON, CSV, TSV, Anki
- 🛡️ Anti-detection với random delays và real browser fingerprints
- 🏗️ Kiến trúc SOLID, dễ mở rộng

## Installation

```bash
# Clone repo
git clone https://github.com/DPz102/quizet-private-flashcard-scraper.git
cd quizet-private-flashcard-scraper

# Create virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows PowerShell
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Usage

### Basic Usage

```bash
# Run with interactive login
python -m src.main

# With username (will prompt for password)
python -m src.main -u your_email@example.com

# Scrape specific sets
python -m src.main -s "https://quizlet.com/123456789/set-name-flash-cards"

# Export to multiple formats
python -m src.main -f json csv anki

# Run headless (after first login)
python -m src.main --headless
```

### Programmatic Usage

```python
from src.utils.config import ConfigLoader
from src.main import QuizletScraper

config = ConfigLoader("config.yaml")
scraper = QuizletScraper(config)

# Login
scraper.login("your_email", "your_password")

# Discover all sets
sets = scraper.discover_sets()

# Scrape specific sets
scraped = scraper.scrape_sets([s.url for s in sets])

# Export
paths = scraper.export(scraped, formats=["json", "csv"])

scraper.close()
```

## Configuration

Edit `config.yaml`:

```yaml
browser:
  headless: false  # Set true after initial login
  slow_mo: 100     # Delay between actions (ms)

scraper:
  delay_min: 2.0   # Min delay between requests (s)
  delay_max: 5.0   # Max delay between requests (s)

export:
  output_dir: "output"
  formats:
    - json
    - csv
```

## Project Structure

```
├── src/
│   ├── core/           # Interfaces & exceptions (DIP)
│   │   ├── interfaces.py
│   │   └── exceptions.py
│   ├── auth/           # Authentication (SRP)
│   │   ├── browser_manager.py
│   │   └── authenticator.py
│   ├── scraper/        # Scraping logic (SRP)
│   │   ├── base_scraper.py
│   │   ├── library_scraper.py
│   │   └── set_scraper.py
│   ├── export/         # Exporters (OCP)
│   │   ├── json_exporter.py
│   │   ├── csv_exporter.py
│   │   ├── anki_exporter.py
│   │   └── exporter_factory.py
│   ├── utils/          # Utilities
│   │   ├── config.py
│   │   └── logging_config.py
│   └── main.py         # Orchestrator
├── auth/               # Session storage (gitignored)
├── output/             # Export output
├── config.yaml
└── requirements.txt
```

## SOLID Principles Applied

| Principle | Implementation |
|-----------|----------------|
| **S**ingle Responsibility | Each class has one job: `Authenticator` = auth, `SetScraper` = scraping |
| **O**pen/Closed | `BaseExporter` is closed for modification, open for extension |
| **L**iskov Substitution | `TSVExporter` can replace `CSVExporter` anywhere |
| **I**nterface Segregation | Small, focused interfaces: `IAuthenticator`, `IExporter`, `IScraper` |
| **D**ependency Inversion | High-level `QuizletScraper` depends on abstractions, not concretions |

## Legal Notice

⚠️ **Important:**
- Chỉ scrape data bạn có quyền truy cập hợp pháp
- Tool này dành cho backup cá nhân
- Tuân thủ Terms of Service của Quizlet
- Không redistribute nội dung đã scrape

## License

MIT License
