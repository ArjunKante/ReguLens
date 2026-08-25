"""Local filesystem storage for uploaded/downloaded evidence and generated
reports (Section 5/8/28/32).

Security properties enforced here:
- Every generated filename is a fresh UUID + a whitelisted extension —
  user-supplied filenames are never used directly as a path component, which
  eliminates path traversal by construction (Section 28).
- Every write is verified, after resolving `..`/symlinks, to land inside
  STORAGE_ROOT before being trusted.
- Original evidence is never overwritten (Section 8: "Never overwrite
  original evidence") — callers always get a brand-new path.
"""
from __future__ import annotations

import mimetypes
import uuid
from pathlib import Path

from app.core.config import get_settings

settings = get_settings()

ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf"}
ALLOWED_UPLOAD_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS


class UnsafeUploadError(ValueError):
    """Raised when an upload fails MIME/extension/size validation."""


def _resolve_within_root(path: Path) -> Path:
    root = settings.storage_path.resolve()
    resolved = path.resolve()
    if root not in resolved.parents and resolved != root:
        raise UnsafeUploadError(f"Refusing to write outside storage root: {resolved}")
    return resolved


def _ext_for(filename: str | None, content_type: str | None) -> str:
    ext = Path(filename).suffix.lower() if filename else ""
    if ext in ALLOWED_UPLOAD_EXTENSIONS:
        return ext
    guessed = mimetypes.guess_extension(content_type) if content_type else None
    if guessed and guessed.lower() in ALLOWED_UPLOAD_EXTENSIONS:
        return guessed.lower()
    return ""


def validate_upload(filename: str | None, content_type: str | None, size_bytes: int) -> str:
    """Returns the safe extension to use, or raises UnsafeUploadError."""
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise UnsafeUploadError(f"File exceeds the {settings.max_upload_size_mb}MB upload limit.")
    ext = _ext_for(filename, content_type)
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise UnsafeUploadError(
            f"Unsupported file type '{filename}' ({content_type}). "
            f"Allowed: {sorted(ALLOWED_UPLOAD_EXTENSIONS)}."
        )
    return ext


def _inspection_dir(inspection_id: uuid.UUID, subdir: str) -> Path:
    path = settings.storage_path / "uploads" / str(inspection_id) / subdir
    path.mkdir(parents=True, exist_ok=True)
    return _resolve_within_root(path)


def save_raw_html(inspection_id: uuid.UUID, html: str) -> str:
    directory = _inspection_dir(inspection_id, "html")
    filename = f"{uuid.uuid4()}.html"
    path = _resolve_within_root(directory / filename)
    path.write_text(html, encoding="utf-8")
    return str(path)


def save_image_bytes(
    inspection_id: uuid.UUID,
    content: bytes,
    *,
    original_filename: str | None,
    content_type: str | None,
    subdir: str = "images",
) -> tuple[str, str]:
    """Validates and persists image bytes. Returns (absolute_path, safe_filename)."""
    ext = validate_upload(original_filename, content_type, len(content))
    directory = _inspection_dir(inspection_id, subdir)
    safe_filename = f"{uuid.uuid4()}{ext}"
    path = _resolve_within_root(directory / safe_filename)
    path.write_bytes(content)
    return str(path), safe_filename


def save_report_bytes(inspection_id: uuid.UUID, content: bytes, *, extension: str) -> str:
    directory = settings.storage_path / "reports" / str(inspection_id)
    directory.mkdir(parents=True, exist_ok=True)
    directory = _resolve_within_root(directory)
    filename = f"{uuid.uuid4()}.{extension.lstrip('.')}"
    path = _resolve_within_root(directory / filename)
    path.write_bytes(content)
    return str(path)


def read_bytes(path: str) -> bytes:
    resolved = _resolve_within_root(Path(path))
    return resolved.read_bytes()
