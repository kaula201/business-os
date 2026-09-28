"""Controlled on-disk paths. Client-supplied paths outside the storage root are rejected."""
import os
import re
import uuid
from pathlib import Path

_SAFE_EXT = re.compile(r"[a-z0-9]{1,8}")


class UnsafeStoragePath(ValueError):
    """Raised when a path escapes the configured storage root."""


def storage_root() -> Path:
    override = os.environ.get("UPLOAD_DIR", "").strip()
    if override:
        root = Path(override)
    else:
        # backend/uploads
        root = Path(__file__).resolve().parents[2] / "uploads"
    return root.resolve()


def document_storage_root() -> Path:
    root = (storage_root() / "documents").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_storage_path(file_path: str, root: Path | None = None) -> Path:
    """Resolve `file_path` and require it to stay inside `root`."""
    if not file_path or "\x00" in file_path:
        raise UnsafeStoragePath("ფაილის გზა დაუშვებელია")
    base = (root or document_storage_root()).resolve()
    candidate = Path(file_path)
    if not candidate.is_absolute():
        candidate = base / candidate
    resolved = candidate.resolve()
    if resolved != base and not resolved.is_relative_to(base):
        raise UnsafeStoragePath("ფაილის გზა დაშვებული საცავის გარეთაა")
    if resolved == base:
        raise UnsafeStoragePath("ფაილის გზა დაუშვებელია")
    return resolved


def allocate_document_path(company_id: str, filename: str) -> Path:
    """Server-chosen path under the document storage root. Ignores client directories."""
    ext = ""
    if filename and "." in filename:
        raw = filename.rsplit(".", 1)[-1].lower()
        if _SAFE_EXT.fullmatch(raw):
            ext = raw
    directory = document_storage_root() / str(company_id)
    directory.mkdir(parents=True, exist_ok=True)
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    path = (directory / stored).resolve()
    if not path.is_relative_to(document_storage_root()):
        raise UnsafeStoragePath("ფაილის გზა დაშვებული საცავის გარეთაა")
    return path
