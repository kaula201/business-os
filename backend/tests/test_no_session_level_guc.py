"""Static checks: app code must not create session-level app.* GUC settings."""
import re
from pathlib import Path

import pytest

_SET_CONFIG_RE = re.compile(r"(?i)\bset_config\s*\(")
_BAD_SET_RE = re.compile(r"(?i)\bSET\s+(?!LOCAL\b)(?:SESSION\s+)?app\.")


def _line_number(source: str, pos: int) -> int:
    return source.count("\n", 0, pos) + 1


def _find_matching_paren(source: str, open_idx: int) -> int | None:
    depth = 0
    i = open_idx
    quote = None
    while i < len(source):
        c = source[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        else:
            if c in ("'", '"'):
                quote = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    return None


def _split_top_level_args(text: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    quote = None
    i = 0
    while i < len(text):
        c = text[i]
        if quote is not None:
            if c == "\\":
                i += 2
                continue
            if c == quote:
                quote = None
        else:
            if c in ("'", '"'):
                quote = c
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            elif c == "," and depth == 0:
                parts.append(text[start:i].strip())
                start = i + 1
        i += 1
    parts.append(text[start:].strip())
    return parts


def _string_literal_content(arg: str) -> str | None:
    arg = arg.strip()
    if len(arg) >= 2 and arg[0] in ("'", '"') and arg[-1] == arg[0]:
        return arg[1:-1]
    return None


def _set_config_violations(source: str) -> list[int]:
    violations = []
    for match in _SET_CONFIG_RE.finditer(source):
        close_idx = _find_matching_paren(source, match.start() + len("set_config(") - 1)
        if close_idx is None:
            continue
        args_text = source[match.end() : close_idx]
        args = _split_top_level_args(args_text)
        if not args:
            continue
        first_value = _string_literal_content(args[0])
        if not first_value or not first_value.startswith("app."):
            continue
        last_raw = args[-1].strip()
        last_value = _string_literal_content(last_raw)
        if last_value is not None:
            last_is_true = last_value.lower() == "true"
        else:
            last_is_true = last_raw.lower() == "true"
        if not last_is_true:
            violations.append(_line_number(source, match.start()))
    return violations


def _bad_set_lines(source: str) -> list[int]:
    return [
        _line_number(source, match.start())
        for match in _BAD_SET_RE.finditer(source)
    ]


def test_scanner_functions_self_test():
    positives = [
        "set_config('app.rls_bypass','on',false)",
        "SET app.current_company_id = 'x'",
        "SET SESSION app.x = 1",
    ]
    negatives = [
        "set_config('app.x', :cid, true)",
        "SET LOCAL app.x = 1",
        "RESET app.rls_bypass",
        "set_config('other.x','1',false)",
    ]
    for sample in positives:
        assert _set_config_violations(sample) or _bad_set_lines(sample), sample
    for sample in negatives:
        assert not _set_config_violations(sample), sample
        assert not _bad_set_lines(sample), sample


def test_no_session_level_set_config_or_set_in_app():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    violations: list[str] = []
    for path in app_dir.rglob("*.py"):
        source = path.read_text()
        for lineno in _set_config_violations(source):
            violations.append(f"{path}:{lineno}: set_config('app.*') missing true")
        for lineno in _bad_set_lines(source):
            violations.append(f"{path}:{lineno}: non-LOCAL SET app.*")
    assert not violations, "\n".join(violations)
