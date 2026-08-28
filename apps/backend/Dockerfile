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
# tesseract-ocr-hin: Hindi/Devanagari trained data — Rule 9(4) permits
# mandatory declarations in Hindi or English, so OCR must read both, not
# just English (see docs/ocr.md). fonts-lohit-deva: a small Devanagari font
# so the Hindi OCR round-trip test can render real Devanagari text without
# a large font dependency.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    libtesseract-dev \
    curl \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    fonts-lohit-deva \
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

# Migrations + rule loading run on every container start, not just under
# docker-compose's separate override of this same sequence (kept there too,
# redundant but harmless) — so the image is correct standalone on any host
# (Render, a bare `docker run`, ...) without needing a platform-specific
# Start Command. Both steps are idempotent (alembic no-ops at head; the rule
# loader logs "unchanged" for rules already loaded), so re-running them on
# every restart is safe. Shell form, not exec-form CMD [...], so $PORT
# expands: Render assigns a dynamic port via $PORT and expects the process
# to bind to it; defaults to 8000 when $PORT is unset (plain `docker run`).
# `exec` on the final command replaces the shell with uvicorn as the
# container's PID 1 child, so it receives SIGTERM directly on shutdown/
# redeploy instead of the shell swallowing it and forcing a slower kill-
# timeout wait (Docker itself flags shell-form CMD without this).
CMD alembic upgrade head && python -m app.rules.loader && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
