# Quizlet Flashcard Scraper

Công cụ scrape flashcards từ Quizlet.

## Cài đặt

```bash
pip install -r requirements.txt
```

## Cấu hình

1. Copy `.env.example` → `.env`
2. Điền thông tin đăng nhập và URLs:

```env
# Thông tin đăng nhập Quizlet
QUIZLET_EMAIL=your_email@example.com
QUIZLET_PASSWORD=your_password

# Danh sách URLs (mỗi URL một dòng, kết thúc bằng dấu phẩy)
QUIZLET_SET_URLS=
    https://quizlet.com/vn/123456/set1-flash-cards/,
    https://quizlet.com/vn/789012/set2-flash-cards/,
```

## Sử dụng

```bash
# Login với email/password
python main.py login auto

# Login thủ công (Google/Facebook OAuth)
python main.py login manual

# Scrape flashcards
python main.py scrape
```

**Lưu ý:** Mỗi lần login sẽ tự động xóa session cũ để tránh xung đột.

## Định dạng output

File được lưu tại `output/<tên-set>.txt`:

```
Câu hỏi 1
A. Đáp án A
B. Đáp án B
[da]B
[ch]
Câu hỏi 2
[da]Định nghĩa 2
```

- `[ch]` = phân cách giữa các card
- `[da]` = phân cách giữa câu hỏi và đáp án

## Yêu cầu hệ thống

- **Python**: 3.9 trở lên
- **OS**: Windows / macOS / Linux
- **Browser**: Google Chrome (phiên bản mới nhất)
- **Patchright**: Playwright fork bypass Cloudflare (tự cài qua requirements.txt)


