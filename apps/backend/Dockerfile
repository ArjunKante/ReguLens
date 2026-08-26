# LM-SCAN backend image: FastAPI + Playwright (Chromium) + Tesseract OCR.
# Pinned to bookworm (Debian 12), not the rolling `slim` tag: Playwright's
# --with-deps installer only officially supports Debian 11/12 and Ubuntu
# 20.04/22.04/24.04. `python:3.11-slim` now resolves to trixie (Debian 13),
# which isn't in that list and causes --with-deps to fall back to an
# Ubuntu 20.04 package set that doesn't exist on trixie (missing
# ttf-ubuntu-font-family / ttf-unifont), failing the build.
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System dependencies: Tesseract OCR engine + libs Playwright's Chromium needs.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    libtesseract-dev \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpangocairo-1.0-0 libpango-1.0-0 libcairo2 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY . .

RUN mkdir -p /app/storage/uploads /app/storage/reports

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
