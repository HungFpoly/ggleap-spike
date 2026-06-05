# Image nền Playwright đã có sẵn Chromium + mọi thư viện hệ thống
FROM mcr.microsoft.com/playwright/python:v1.47.0-jammy

# In log real-time, không đệm stdout (quan trọng khi xem log trên Render)
ENV PYTHONUNBUFFERED=1

WORKDIR /app
COPY check_recaptcha.py .

# playwright đã có sẵn trong base image; cài lại cho chắc phiên bản khớp
RUN pip install --no-cache-dir playwright==1.47.0

# Chạy 1 lần rồi thoát (one-shot) — phù hợp Render "Job"
CMD ["python", "check_recaptcha.py"]
