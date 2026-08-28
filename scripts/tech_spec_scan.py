#!/usr/bin/env python3
"""Business OS — Tech Spec auto-scanner.

Scans frontend pages (buttons, filters, tables, API calls) and backend
endpoints, then writes machine-readable JSON snapshots into
docs/tech-spec/_scan/ so the tech spec can be kept in sync with code.

Usage:
    python scripts/tech_spec_scan.py [--out docs/tech-spec/_scan]

Outputs:
    _scan/pages.json      — per-page UI inventory (buttons, filters, selects)
    _scan/endpoints.json  — per-endpoint-file API inventory
    _scan/summary.json    — counts + last scan time
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGES_DIR = ROOT / "frontend" / "src" / "pages"
ENDPOINTS_DIR = ROOT / "backend" / "app" / "api" / "v1" / "endpoints"
API_TS = ROOT / "frontend" / "src" / "services" / "api.ts"

# ── regexes ──────────────────────────────────────────────────────────────────

# t('...') translation keys inside a button
T_KEY_RE = re.compile(r"t\(\s*['\"]([^'\"]+)['\"]\s*\)")
# aria-label="..."
ARIA_RE = re.compile(r"aria-label\s*=\s*[\"']([^\"']+)[\"']")
# disabled={...}
DISABLED_RE = re.compile(r"disabled\s*=\s*\{([^}]*)\}")
# <select ...>...</select>
SELECT_RE = re.compile(r"<select\b(?P<attrs>[^>]*)>(?P<inner>.*?)</select>", re.S | re.I)
# <option value="...">label</option>
OPTION_RE = re.compile(r"<option\b[^>]*value\s*=\s*[\"']([^\"']*)[\"'][^>]*>(.*?)</option>", re.S | re.I)
# <input ...> with placeholder / aria-label
INPUT_RE = re.compile(r"<input\b(?P<attrs>[^>]*?)/?>", re.S | re.I)
ATTR_RE = re.compile(r"([\w-]+)\s*=\s*[\"']([^\"']*)[\"']")
# api.get/post/patch/put/delete('/path', ...)
API_CALL_RE = re.compile(
    r"\bapi\.(get|post|patch|put|delete)\s*\(\s*[`'\"]"
    r"(?P<path>[^`'\"]+)",
)
# xxxApi.method('path') / xxxApi.method({...}) — page-level API client calls
API_CLIENT_RE = re.compile(
    r"\b(?P<client>\w+Api)\.(?P<method>get|post|patch|put|delete|list|create|update|remove|toggle|export|import)\s*\(\s*(?:[`'\"]?(?P<path>[^`'\"),}]+))?",
)
# FastAPI route decorators (path may be empty string "")
ROUTE_RE = re.compile(
    r"@router\.(get|post|patch|put|delete)\s*\(\s*[\"'](?P<path>[^\"']*)[\"']",
)
DOCSTRING_RE = re.compile(r'"""(?P<doc>.*?)"""', re.S)
# router prefix
PREFIX_RE = re.compile(r'APIRouter\(prefix\s*=\s*["\']([^"\']+)["\']')
# module code from page filename: InvoicesPage.tsx -> invoices
PAGE_CODE_RE = re.compile(r"^(?P<code>[A-Za-z0-9-]+)Page\.tsx$")


# ── JSX-aware helpers ────────────────────────────────────────────────────────


def _skip_jsx_attrs(src: str, start: int) -> int | None:
    """From the char after '<button', return index of the closing '>'.

    Handles backtick template literals (which may contain '>' and ${...})
    and quoted attribute values. Returns None if unbalanced.
    """
    i = start
    in_backtick = False
    while i < len(src):
        c = src[i]
        if in_backtick:
            if c == "`":
                in_backtick = False
            elif c == "$" and i + 1 < len(src) and src[i + 1] == "{":
                # skip ${...} with nested braces
                j = i + 2
                d = 1
                while j < len(src) and d > 0:
                    if src[j] == "{":
                        d += 1
                    elif src[j] == "}":
                        d -= 1
                    j += 1
                i = j
                continue
            i += 1
            continue
        if c == "`":
            in_backtick = True
            i += 1
            continue
        if c in "\"'":
            # skip quoted attribute value
            q = c
            i += 1
            while i < len(src) and src[i] != q:
                i += 1
            i += 1
            continue
        if c == "{":
            # skip balanced {...} expression (may contain => arrows with '>')
            j = i + 1
            d = 1
            while j < len(src) and d > 0:
                if src[j] == "{":
                    d += 1
                elif src[j] == "}":
                    d -= 1
                j += 1
            i = j
            continue
        if c == ">":
            return i
        i += 1
    return None


def _find_buttons(src: str):
    """Yield (attrs, inner) for every <button>...</button> in src."""
    pos = 0
    while True:
        start = src.find("<button", pos)
        if start == -1:
            return
        gt = _skip_jsx_attrs(src, start + len("<button"))
        if gt is None:
            return
        attrs = src[start + len("<button"):gt]
        close = src.find("</button>", gt + 1)
        if close == -1:
            return
        inner = src[gt + 1:close]
        yield attrs, inner
        pos = close + len("</button>")


def _balanced_braces(src: str, start: int) -> str | None:
    """Return the text inside the braces starting at src[start] == '{'."""
    depth = 0
    for i in range(start, len(src)):
        c = src[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[start + 1 : i]
    return None


def _find_onclick(attrs: str) -> str | None:
    m = re.search(r"onClick\s*=\s*\{", attrs)
    if not m:
        return None
    body = _balanced_braces(attrs, m.end() - 1)
    if body is None:
        return None
    body = re.sub(r"\s+", " ", body).strip()
    return body[:120]


def clean_text(s: str) -> str:
    """Collapse whitespace and strip JSX braces noise from inner text."""
    s = re.sub(r"\{[^}]*\}", " ", s)  # remove {expressions}
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def extract_label(attrs: str, inner: str) -> str | None:
    """Best-effort human label for a button: t('...') key, aria-label, or text."""
    m = T_KEY_RE.search(inner)
    if m:
        return m.group(1)
    m = ARIA_RE.search(attrs)
    if m:
        return m.group(1)
    text = clean_text(inner)
    # strip icon-only buttons (lucide <X size={20}/> etc.)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


# ── scanners ─────────────────────────────────────────────────────────────────


def scan_page(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    code = PAGE_CODE_RE.match(path.name)
    module_code = code.group("code") if code else path.stem

    buttons = []
    for attrs, inner in _find_buttons(src):
        label = extract_label(attrs, inner)
        if label is None:
            continue
        onclick = _find_onclick(attrs)
        disabled = DISABLED_RE.search(attrs)
        buttons.append({
            "label": label,
            "on_click": onclick,
            "disabled": bool(disabled),
        })

    selects = []
    for m in SELECT_RE.finditer(src):
        attrs, inner = m.group("attrs"), m.group("inner")
        label = ARIA_RE.search(attrs)
        options = [
            {"value": v, "label": clean_text(l)}
            for v, l in OPTION_RE.findall(inner)
        ]
        selects.append({
            "label": label.group(1) if label else None,
            "options": options[:20],
        })

    inputs = []
    for m in INPUT_RE.finditer(src):
        attrs = m.group("attrs")
        attrs_dict = dict(ATTR_RE.findall(attrs))
        if "type" in attrs_dict and attrs_dict["type"] in ("hidden", "submit", "button", "checkbox", "radio"):
            continue
        ph = attrs_dict.get("placeholder") or attrs_dict.get("aria-label")
        if ph:
            inputs.append({"placeholder": ph, "type": attrs_dict.get("type", "text")})

    api_calls = []
    for m in API_CALL_RE.finditer(src):
        api_calls.append({"method": m.group(1).upper(), "path": m.group(2)})
    for m in API_CLIENT_RE.finditer(src):
        api_calls.append({
            "method": m.group("method").upper(),
            "path": m.group("path") or "",
            "client": m.group("client"),
        })

    return {
        "module_code": module_code,
        "file": str(path.relative_to(ROOT)),
        "lines": src.count("\n") + 1,
        "buttons": buttons,
        "selects": selects,
        "inputs": inputs,
        "api_calls": api_calls,
    }


def scan_endpoint(path: Path) -> dict:
    src = path.read_text(encoding="utf-8")
    prefix_m = PREFIX_RE.search(src)
    prefix = prefix_m.group(1) if prefix_m else ""

    routes = []
    for m in ROUTE_RE.finditer(src):
        method = m.group(1).upper()
        route_path = m.group(2)
        # find the function that follows this decorator (multi-line signatures OK)
        after = src[m.end():]
        fm = re.search(
            r"async def (\w+)\s*\((?P<args>.*?)\)\s*:\s*\n(?P<body>.*?)(?=\n@router|\nclass |\Z)",
            after, re.S,
        )
        name = fm.group(1) if fm else "?"
        args = fm.group("args") if fm else ""
        doc = ""
        if fm:
            dm = DOCSTRING_RE.search(fm.group("body"))
            if dm:
                doc = " ".join(dm.group(1).split())[:200]
        routes.append({
            "method": method,
            "path": route_path,
            "full_path": f"{prefix}{route_path}",
            "function": name,
            "doc": doc,
            "auth": "require_admin" in args or "require_admin" in src[m.start():m.end() + 400],
        })

    return {
        "file": str(path.relative_to(ROOT)),
        "prefix": prefix,
        "routes": routes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "docs" / "tech-spec" / "_scan"))
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    pages = []
    for p in sorted(PAGES_DIR.glob("*Page.tsx")):
        try:
            pages.append(scan_page(p))
        except Exception as e:  # noqa: BLE001
            print(f"⚠ skip {p.name}: {e}", file=sys.stderr)

    endpoints = []
    for p in sorted(ENDPOINTS_DIR.glob("*.py")):
        if p.name.startswith("__"):
            continue
        try:
            endpoints.append(scan_endpoint(p))
        except Exception as e:  # noqa: BLE001
            print(f"⚠ skip {p.name}: {e}", file=sys.stderr)

    total_buttons = sum(len(pg["buttons"]) for pg in pages)
    total_routes = sum(len(ep["routes"]) for ep in endpoints)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pages": len(pages),
        "buttons": total_buttons,
        "selects": sum(len(pg["selects"]) for pg in pages),
        "inputs": sum(len(pg["inputs"]) for pg in pages),
        "endpoint_files": len(endpoints),
        "routes": total_routes,
    }

    (out / "pages.json").write_text(
        json.dumps(pages, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "endpoints.json").write_text(
        json.dumps(endpoints, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
