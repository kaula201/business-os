"""Controlled on-disk paths. Client-supplied paths outside the storage root are rejected."""
import os
import re
import uuid
from pathlib import Path

_SAFE_EXT = re.compile(r"[a-z0-9]{1,8}")
_SAFE_CATEGORY = re.compile(r"[a-z][a-z0-9_]{0,31}")


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


def _safe_extension(filename: str) -> str:
    if not filename or "." not in filename:
        return ""
    raw = filename.rsplit(".", 1)[-1].lower()
    return raw if _SAFE_EXT.fullmatch(raw) else ""


def category_storage_root(category: str) -> Path:
    """A single server-chosen directory under the storage root (documents, helpdesk, …)."""
    if not _SAFE_CATEGORY.fullmatch(category):
        raise UnsafeStoragePath("ფაილის გზა დაუშვებელია")
    root = (storage_root() / category).resolve()
    if not root.is_relative_to(storage_root()):
        raise UnsafeStoragePath("ფაილის გზა დაშვებული საცავის გარეთაა")
    root.mkdir(parents=True, exist_ok=True)
    return root


def document_storage_root() -> Path:
    return category_storage_root("documents")


def allocate_stored_file(category: str, company_id: str, filename: str) -> Path:
    """Server-chosen path: `{root}/{category}/{company_id}/{uuid}.{safe_ext}`.

    The client filename is used only to pick a safe extension. It is never a path.
    """
    root = category_storage_root(category)
    directory = (root / str(company_id)).resolve()
    if not directory.is_relative_to(root):
        raise UnsafeStoragePath("ფაილის გზა დაშვებული საცავის გარეთაა")
    directory.mkdir(parents=True, exist_ok=True)
    ext = _safe_extension(filename)
    stored = f"{uuid.uuid4().hex}.{ext}" if ext else uuid.uuid4().hex
    path = (directory / stored).resolve()
    if not path.is_relative_to(root):
        raise UnsafeStoragePath("ფაილის გზა დაშვებული საცავის გარეთაა")
    return path


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
    return allocate_stored_file("documents", company_id, filename)


def allocate_helpdesk_path(company_id: str, filename: str) -> Path:
    """Server-chosen path under `storage_root()/helpdesk/{company_id}`."""
    return allocate_stored_file("helpdesk", company_id, filename)
