# Quizlet Flashcard Scraper

Scrape flashcards từ Quizlet private sets.

## Installation

```bash
pip install -r requirements.txt
```

## Setup

1. Copy `.env.example` → `.env`
2. Điền thông tin:
   ```
   QUIZLET_EMAIL=your_email
   QUIZLET_PASSWORD=your_password
   QUIZLET_SET_URL=https://quizlet.com/vn/xxx/set-name-flash-cards/
   ```

## Usage

```bash
# Step 1: Login (chỉ cần 1 lần)
python main.py login

# Step 2: Scrape
python main.py scrape
```

## Output Format

File `output/flashcards.txt`:
```
Câu hỏi 1
A. Đáp án A
B. Đáp án B
[da]B
[ch]
Câu hỏi 2
[da]Định nghĩa 2
```

- `[ch]` = separator giữa các card
- `[da]` = separator giữa thuật ngữ và định nghĩa

## License

MIT
