# Quizlet Private Flashcard Scraper

Export flashcards từ Quizlet, bao gồm cả private sets được chia sẻ với bạn.

## Features

- 🔐 Đăng nhập và lưu session để tái sử dụng
- 📚 Tự động phát hiện tất cả flashcard sets trong thư viện
- 🔗 Hỗ trợ private sets được share qua classes/folders
- 📤 Export định dạng tương thích Quizlet Import
- 🛡️ Anti-detection với random delays và real browser fingerprints
- 🏗️ Kiến trúc SOLID, dễ mở rộng

## Installation

```bash
# Clone repo
git clone https://github.com/DPz102/quizlet-private-flashcard-scraper.git
cd quizlet-private-flashcard-scraper

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

### Flow 1: Discover (Đăng nhập & Quét thư viện)

```bash
# Đăng nhập và quét danh sách flashcard sets
python -m src.main discover

# Hoặc với username (sẽ prompt password)
python -m src.main discover -u your_email@example.com
```

**Output:**
- Session được lưu vào `auth/quizlet_session.json`
- Metadata được lưu vào `output/sets_metadata.json`

### Flow 2: Scrape (Cào nội dung)

```bash
# Scrape 1 set cụ thể bằng ID (từ metadata)
python -m src.main scrape --set-id 123456789

# Scrape bằng URL trực tiếp
python -m src.main scrape --url "https://quizlet.com/123456789/set-name-flash-cards"

# Scrape tất cả sets đã discover
python -m src.main scrape --all
```

**Output:** File `output/export_<set_id>_<title>.txt`

### Flow 3: Logout (Đổi tài khoản)

```bash
# Xóa session hiện tại
python -m src.main logout

# Sau đó chạy discover để đăng nhập tài khoản mới
python -m src.main discover
```

## Export Format

File export sử dụng custom tags để tương thích với Quizlet Import:

```
term1/answer/definition1/question/term2/answer/definition2
```

### Import vào Quizlet

1. Mở file `export_*.txt`
2. Copy toàn bộ nội dung (bỏ qua dòng comment `#`)
3. Vào Quizlet → Create → Import
4. Paste nội dung
5. Cài đặt:
   - **Between term and definition:** `/answer/`
   - **Between cards:** `/question/`
6. Click Import

### Ví dụ Export

```
# Biology Chapter 1
# Set ID: 123456789
# Cards: 3
# Import settings for Quizlet:
#   Between term and definition: /answer/
#   Between cards: /question/

Mitochondria/answer/Powerhouse of the cell/question/DNA/answer/Deoxyribonucleic acid/question/RNA/answer/Ribonucleic acid
```

## Project Structure

```
├── src/
│   ├── core/           # Interfaces & exceptions
│   ├── auth/           # Authentication (SRP)
│   │   ├── browser_manager.py
│   │   └── authenticator.py
│   ├── scraper/        # Scraping logic (SRP)
│   │   ├── base_scraper.py
│   │   ├── library_scraper.py
│   │   └── set_scraper.py
│   ├── export/         # Exporter
│   │   └── quizlet_exporter.py
│   ├── utils/          # Utilities
│   └── main.py         # Orchestrator
├── auth/               # Session storage (gitignored)
├── output/             # Export output
│   ├── sets_metadata.json
│   └── export_*.txt
├── config.yaml
└── requirements.txt
```

## Configuration

Edit `config.yaml`:

```yaml
browser:
  headless: false  # Set true sau khi login lần đầu
  slow_mo: 100     # Delay giữa actions (ms)

scraper:
  delay_min: 2.0   # Min delay giữa requests (s)
  delay_max: 5.0   # Max delay giữa requests (s)

export:
  output_dir: "output"
```

## Legal Notice

⚠️ **Lưu ý:**
- Chỉ scrape data bạn có quyền truy cập hợp pháp
- Tool này dành cho backup cá nhân
- Tuân thủ Terms of Service của Quizlet
- Không redistribute nội dung đã scrape

## License

MIT License
