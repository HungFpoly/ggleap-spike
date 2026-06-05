# Spike: Kiểm tra reCAPTCHA / IP

Mục tiêu duy nhất: trả lời câu hỏi **"IP của Render có vượt được reCAPTCHA v3 của ggleap và lấy được dữ liệu không?"** — trước khi xây cả hệ thống.

Script `check_recaptcha.py` mở trang booking của 3 quán bằng Chromium (Playwright), thử 2 cách lấy dữ liệu:
- **interception**: nghe response mà chính trang tự gọi (token do trang sinh).
- **in-page fetch**: tự dò siteKey, gọi `grecaptcha.execute()` lấy token, rồi `fetch()` API.

Kết quả in ra HTTP status cho từng quán và một dòng tổng kết PASS/FAIL.

---

## Bước 1: Chạy thử trên máy bạn (IP dân dụng — kỳ vọng PASS)

```bash
cd spike
pip install playwright==1.47.0
python -m playwright install chromium
python check_recaptcha.py
```

Đọc dòng cuối:
- `=> IP NÀY VƯỢT ĐƯỢC reCAPTCHA` → tốt, cơ chế lấy token chạy đúng.
- Nếu máy bạn cũng FAIL → có thể siteKey/action chưa đúng; xem log `siteKey tìm thấy:` và các dòng `action=...`.

> Mục đích của bước này là xác nhận **code đúng** trên một IP "sạch". Phép thử thật nằm ở bước 2 (Render).

---

## Bước 2: Chạy trên Render (IP datacenter — đây mới là phép thử quyết định)

Render chạy script này như một **Job** (chạy 1 lần rồi thoát). Cách làm:

### Cách A — Deploy bằng Docker qua Git (khuyến nghị)

1. Đẩy thư mục `spike/` này lên một Git repo (GitHub/GitLab).
2. Trên Render dashboard: **New +** → **Background Worker** (hoặc **Cron Job** nếu UI không có Job rời).
   - Nếu chọn **Cron Job**: đặt `Schedule` tạm là `0 0 1 1 *` (gần như không bao giờ tự chạy), rồi bấm **Trigger Run** thủ công để chạy ngay.
3. Cấu hình:
   - **Region**: `Frankfurt (EU Central)` ← quan trọng, đúng vùng sẽ dùng thật.
   - **Runtime**: `Docker`.
   - **Dockerfile Path**: `spike/Dockerfile` (hoặc `./Dockerfile` nếu repo chỉ chứa nội dung spike).
   - **Instance Type**: gói nhỏ nhất có RAM ≥ 512MB.
4. Tạo xong → **Trigger Run** / xem **Logs**.

### Cách B — Không dùng Git

Render cần nguồn từ Git hoặc image registry. Nếu không muốn dùng Git:
- Build image rồi push lên Docker Hub:
  ```bash
  cd spike
  docker build -t <user>/ggleap-spike:latest .
  docker push <user>/ggleap-spike:latest
  ```
- Trên Render: **New +** → **Background Worker** → **Deploy an existing image** → điền `<user>/ggleap-spike:latest`, chọn region **Frankfurt**.

---

## Đọc kết quả trên Render Logs

Tìm khối `KẾT QUẢ` ở cuối log:

```
  MVP            interception=200 in-page=200  -> PASS (200)
  MVP Brno       interception=200 in-page=200  -> PASS (200)
  Cyber Empire   interception=200 in-page=200  -> PASS (200)
=> IP NÀY VƯỢT ĐƯỢC reCAPTCHA. An toàn để xây hệ thống chính.
```

| Tín hiệu | Ý nghĩa | Hành động |
|----------|---------|-----------|
| `PASS (200)` cho cả 3 | IP Render qua được reCAPTCHA | Yên tâm xây hệ thống chính, không cần proxy |
| `FAIL`, status `403` | reCAPTCHA chấm điểm thấp IP datacenter | Thử thêm stealth; nếu vẫn 403 → cần **proxy residential** |
| status `-1` | lỗi mạng/JS trong trang | Xem dòng body để biết chi tiết |
| `x-country-code` lạ | nghi geo-block | Kiểm tra lại region = Frankfurt |
| `siteKey tìm thấy: None` | chưa dò được siteKey | Vẫn có thể PASS nhờ interception; nếu cần, chỉnh `JS_FIND_SITEKEY` |

---

## Nếu Render bị 403 (kịch bản xấu nhưng cần lường trước)

1. **Bật stealth**: thêm `playwright-stealth` để ẩn `navigator.webdriver`...
2. **Proxy residential**: launch Chromium với `proxy={"server": "...", "username": "...", "password": "..."}`. Đây là cách chắc ăn nhất khi IP datacenter bị từ chối.

Khi xác nhận được hướng đi (qua được hay phải proxy), mình sẽ áp dụng đúng cấu hình đó vào hệ thống chính rồi mới build tiếp.
