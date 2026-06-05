"""
Spike: Kiểm tra IP hiện tại (máy bạn / Render) có vượt được reCAPTCHA v3 của ggleap
và lấy được dữ liệu PC trống hay không.

Đây là proof-of-concept ĐỘC LẬP với hệ thống chính. Mục tiêu duy nhất:
trả lời câu hỏi "IP này có nhận HTTP 200 từ public_booking_available_devices không?"

Chạy:  python check_recaptcha.py
Thoát code 0 nếu có ÍT NHẤT một quán trả 200; ngược lại thoát code 1.
"""

import sys
import json
from datetime import datetime, timedelta, timezone

from playwright.sync_api import sync_playwright

BOOKING_BASE = "https://centers.ggcircuit.com"
API_URL = "https://api.ggleap.com/production/public_booking_available_devices"

# 3 quán cần kiểm tra (slug + centerUuid)
VENUES = [
    {"slug": "mvp", "name": "MVP", "uuid": "f71515f0-3c74-46d7-9a92-6bd582c9b966"},
    {"slug": "mvpbrn", "name": "MVP Brno", "uuid": "222b2b2c-e92e-412b-9180-5702652c11a7"},
    {"slug": "cyberempire", "name": "Cyber Empire", "uuid": "8e75d6f4-4e81-427c-9b40-3161d2664798"},
]

# reCAPTCHA v3 cần action; ta thử vài action phổ biến, dừng ở cái nào ra 200
CANDIDATE_ACTIONS = ["submit", "booking", "search", "homepage", "search_booking"]

# ---- JS chạy trong ngữ cảnh trang ----

JS_FIND_SITEKEY = r"""
() => {
  // 1) script src .../api.js?render=SITEKEY
  for (const s of document.querySelectorAll('script')) {
    const m = (s.src || '').match(/[?&]render=([\w-]+)/);
    if (m && m[1] && m[1] !== 'explicit') return m[1];
  }
  // 2) thẻ data-sitekey
  const el = document.querySelector('[data-sitekey]');
  if (el) return el.getAttribute('data-sitekey');
  // 3) đào trong cấu hình nội bộ của grecaptcha
  try {
    const cfg = window.___grecaptcha_cfg;
    if (cfg && cfg.clients) {
      for (const k of Object.keys(cfg.clients)) {
        const c = cfg.clients[k];
        const found = JSON.stringify(c).match(/"sitekey":"([\w-]+)"/);
        if (found) return found[1];
      }
    }
  } catch (e) {}
  return null;
}
"""

JS_GET_TOKEN = r"""
async ({siteKey, action}) => {
  // Trang có thể dùng reCAPTCHA thường (grecaptcha) hoặc Enterprise (grecaptcha.enterprise)
  const gre = (window.grecaptcha && window.grecaptcha.enterprise)
    ? window.grecaptcha.enterprise
    : window.grecaptcha;
  if (!gre || !gre.execute) {
    return {ok: false, error: 'grecaptcha(.enterprise) không khả dụng',
            diag: {hasGrecaptcha: !!window.grecaptcha,
                   hasEnterprise: !!(window.grecaptcha && window.grecaptcha.enterprise),
                   keys: window.grecaptcha ? Object.keys(window.grecaptcha) : []}};
  }
  try {
    await new Promise((res) => {
      if (gre.ready) gre.ready(res); else res();
    });
    const token = await gre.execute(siteKey, {action});
    return {ok: true, token};
  } catch (e) {
    return {ok: false, error: String(e)};
  }
}
"""

JS_FETCH = r"""
async ({url, params, token}) => {
  const qs = new URLSearchParams(params).toString();
  try {
    const r = await fetch(`${url}?${qs}`, {
      headers: {
        'g-recaptcha-token': token,
        'x-gg-client': 'DynamicCenterPagesWeb 0.1',
        'accept': 'application/json, text/plain, */*'
      }
    });
    const body = await r.text();
    return {status: r.status, body: body.slice(0, 400),
            country: r.headers.get('x-country-code')};
  } catch (e) {
    return {status: -1, body: String(e), country: null};
  }
}
"""


def time_window():
    """Một khung giờ hợp lệ trong tương lai gần, định dạng ISO8601 UTC như site dùng.
    API yêu cầu: start cách hiện tại TỐI THIỂU 15 phút VÀ làm tròn về mốc 15 phút (00/15/30/45)."""
    now = datetime.now(timezone.utc)
    target = now + timedelta(minutes=20)          # đảm bảo > 15 phút
    # làm tròn LÊN mốc 15 phút gần nhất
    minute = (target.minute // 15 + 1) * 15
    if minute >= 60:
        target = target.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        target = target.replace(minute=minute, second=0, microsecond=0)
    start = target
    end = start + timedelta(hours=1)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    return start.strftime(fmt), end.strftime(fmt)


def check_venue(page, venue):
    """Mở trang booking của 1 quán, thử lấy token + gọi API. Trả về dict kết quả."""
    result = {"venue": venue["name"], "intercepted": None, "inpage": None}
    start, end = time_window()

    # (a) Lắng nghe response mà CHÍNH trang tự gọi (ground truth, token do trang sinh)
    captured = {}

    def on_response(resp):
        if "public_booking_available_devices" in resp.url and "intercept_status" not in captured:
            captured["intercept_status"] = resp.status
            captured["intercept_url"] = resp.url

    page.on("response", on_response)

    url = f"{BOOKING_BASE}/{venue['slug']}/search-booking"
    print(f"\n=== {venue['name']} ===")
    print(f"  mở {url}")
    # KHÔNG dùng networkidle: trang có request nền liên tục (reCAPTCHA/polling) nên không bao giờ idle.
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    # Chủ động đợi grecaptcha sẵn sàng (tối đa ~25s), thay vì đợi network idle.
    try:
        page.wait_for_function(
            "() => (window.grecaptcha && window.grecaptcha.execute) || "
            "(window.grecaptcha && window.grecaptcha.enterprise && window.grecaptcha.enterprise.execute)",
            timeout=25000,
        )
        print("  grecaptcha đã sẵn sàng")
    except Exception:
        print("  CẢNH BÁO: grecaptcha chưa sẵn sàng sau 25s (vẫn thử tiếp)")
    page.wait_for_timeout(4000)  # chờ trang tự gọi API (nếu có)

    if "intercept_status" in captured:
        result["intercepted"] = captured["intercept_status"]
        print(f"  [interception] trang tự gọi API -> HTTP {captured['intercept_status']}")
        print(f"  [interception] URL trang gọi: {captured.get('intercept_url')}")
    else:
        print("  [interception] trang không tự gọi API trong lúc chờ")

    # (b) In-page fetch: tự lấy siteKey + token rồi gọi API
    site_key = page.evaluate(JS_FIND_SITEKEY)
    print(f"  siteKey tìm thấy: {site_key}")

    if site_key:
        for action in CANDIDATE_ACTIONS:
            tok = page.evaluate(JS_GET_TOKEN, {"siteKey": site_key, "action": action})
            if not tok.get("ok"):
                print(f"  [token] action='{action}' lỗi: {tok.get('error')}")
                if tok.get("diag"):
                    print(f"          diag: {tok.get('diag')}")
                break
            res = page.evaluate(JS_FETCH, {
                "url": API_URL,
                "params": {"centerUuid": venue["uuid"], "start": start, "end": end},
                "token": tok["token"],
            })
            print(f"  [in-page] action='{action}' -> HTTP {res['status']} "
                  f"(x-country-code={res.get('country')})")
            result["inpage"] = res["status"]
            if res["status"] == 200:
                print(f"  body: {res['body'][:200]}")
                break
            else:
                print(f"          body: {res['body'][:200]}")
    else:
        print("  [in-page] không tìm được siteKey -> chỉ dựa vào interception")

    page.remove_listener("response", on_response)
    return result


def main():
    print("Spike kiểm tra reCAPTCHA / IP - ggleap public_booking_available_devices")
    # Cho phép lọc theo slug: python check_recaptcha.py mvp
    venues = VENUES
    if len(sys.argv) > 1:
        wanted = set(sys.argv[1:])
        venues = [v for v in VENUES if v["slug"] in wanted]
        print(f"Chỉ chạy: {[v['slug'] for v in venues]}")
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            locale="en-US",
            viewport={"width": 1366, "height": 768},
        )
        page = context.new_page()
        for venue in venues:
            try:
                results.append(check_venue(page, venue))
            except Exception as e:
                print(f"  LỖI khi xử lý {venue['name']}: {e}")
                results.append({"venue": venue["name"], "error": str(e)})
        browser.close()

    # ---- Tổng kết ----
    print("\n================ KẾT QUẢ ================")
    any_200 = False
    for r in results:
        statuses = [r.get("intercepted"), r.get("inpage")]
        ok = 200 in statuses
        any_200 = any_200 or ok
        verdict = "PASS (200)" if ok else "FAIL"
        print(f"  {r['venue']:<14} interception={r.get('intercepted')} "
              f"in-page={r.get('inpage')}  -> {verdict}")
    print("=========================================")
    if any_200:
        print("=> IP NÀY VƯỢT ĐƯỢC reCAPTCHA. An toàn để xây hệ thống chính.")
        sys.exit(0)
    else:
        print("=> IP NÀY BỊ CHẶN (không có 200). Cần proxy residential hoặc stealth.")
        sys.exit(1)


if __name__ == "__main__":
    main()
