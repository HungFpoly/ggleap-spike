# PC Availability Tracker

Thu thập số PC còn trống theo từng zone tại 3 quán gaming cafe (MVP, MVP Brno,
Cyber Empire) trên nền tảng ggleap mỗi giờ, ghi vào Google Sheets để phân tích
pattern lượng khách và hành vi đặt chỗ trước.

- Dùng Playwright (Chromium headless) để vượt reCAPTCHA Enterprise và gọi API
  `public_booking_available_devices`.
- Lấy số PC **thật** (không bị giới hạn ở 5 như giao diện web).
- Mọi nhãn thời gian theo giờ **Europe/Prague** (kể cả thời điểm ghi).
- Chạy one-shot mỗi giờ trên Render Cron Job (region Frankfurt).

## Cấu trúc

```
app/
  config.py          # AppConfig.from_env, 3 Quán mặc định
  models.py          # AvailabilityRecord (4 cột)
  clock.py           # nguồn thời gian giờ Prague
  time_slots.py      # tính Khung_Giờ, DST, luật 15 phút
  response_parser.py # parse JSON ggleap, loại excluded zones
  zone_tracker.py    # trạng thái zone, khử trùng tên trùng
  monitor.py         # giám sát log, thất bại liên tiếp
  browser_manager.py # Playwright Chromium
  ggleap_client.py   # in-page fetch + token enterprise + retry
  sheets_writer.py   # ghi Google Sheets (3 tab + _state)
  orchestrator.py    # điều phối một Chu_Kỳ
  main.py            # entrypoint (--validate / --once / mặc định)
tests/               # unit + property-based (Hypothesis)
```

## Cài đặt & chạy local

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium
pytest -q                     # chạy toàn bộ test
```

Chạy thật (cần Service Account + Spreadsheet, xem bên dưới):

```bash
export GOOGLE_SPREADSHEET_ID=...        # ID của Google Spreadsheet
export GOOGLE_SA_PATH=./service_account.json
python -m app.main --validate           # kiểm tra vượt reCAPTCHA, KHÔNG ghi Sheets
python -m app.main --once               # chạy một Chu_Kỳ, ghi Sheets (demo)
```

## Chuẩn bị Google Sheets (Service Account)

1. Tạo project trên Google Cloud Console, bật **Google Sheets API**.
2. Tạo **Service Account**, tải khóa JSON về (lưu thành `service_account.json`).
3. Tạo một Google Spreadsheet trống, lấy **Spreadsheet ID** từ URL
   (`https://docs.google.com/spreadsheets/d/<ID>/edit`).
4. **Chia sẻ** spreadsheet đó với email của Service Account (dạng
   `...@...iam.gserviceaccount.com`) với quyền **Editor**.
5. Hệ thống tự tạo 3 tab (MVP, MVP Brno, Cyber Empire) + tab `_state`.

## Cấu hình (biến môi trường)

| Biến | Bắt buộc | Mặc định | Ý nghĩa |
|------|----------|----------|---------|
| `GOOGLE_SPREADSHEET_ID` | có | — | ID Google Spreadsheet |
| `GOOGLE_SA_PATH` | có | — | đường dẫn khóa JSON Service Account |
| `LOOK_AHEAD_HOURS` | không | `3` | số Khung_Giờ tương lai thu thập thêm |
| `VENUES_JSON` | không | 3 Quán mặc định | ghi đè danh sách Quán |
| `EXCLUDED_ZONES` | không | `Room for unassigned machines` | zone bị loại |
| `PROXY_ENABLED` | không | `false` | bật proxy dự phòng |
| `PROXY_SERVER` | không | — | chuỗi kết nối proxy residential |

## Triển khai lên Render

1. Đẩy repo lên Git, kết nối với Render.
2. Tạo **Cron Job**: Runtime `Docker`, Region **Frankfurt**, Schedule `44 * * * *`,
   plan có RAM ≥ 512MB (hoặc dùng `render.yaml` sẵn có).
3. Thêm **Secret File** `service_account.json` mount tại
   `/etc/secrets/service_account.json`.
4. Khai báo env `GOOGLE_SPREADSHEET_ID` (và proxy nếu cần).
5. **Trước khi bật chạy định kỳ**, chạy thủ công với lệnh kiểm tra:
   `python -m app.main --validate` để xác nhận vượt được reCAPTCHA (HTTP 200).
   Nếu bị 403, bật `PROXY_ENABLED=true` và cấu hình `PROXY_SERVER`.

## Lưu ý kỹ thuật

- API ggleap yêu cầu `start` cách hiện tại ≥ 15 phút và làm tròn mốc 15 phút →
  hệ thống chạy phút 44 để lấy đúng khung giờ kế tiếp (đầu giờ sau).
- reCAPTCHA là bản **Enterprise**; token lấy qua `grecaptcha.enterprise.execute`.
- Zone trùng tên (vd 3 "Classic zone" ở MVP Brno) được phân biệt theo RoomUuid
  và hiển thị "#1", "#2"... trong cột Zone.
