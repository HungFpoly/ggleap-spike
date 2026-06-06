# Image nền Playwright đã có sẵn Chromium + thư viện hệ thống
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# Log real-time trên Render (không đệm stdout)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# One-shot: chạy một Chu_Kỳ rồi thoát
ENTRYPOINT ["python", "-m", "app.main"]
