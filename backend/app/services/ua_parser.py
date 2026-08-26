"""Parse User-Agent into a human-readable device description (offline, no external deps)."""

import re


def parse_user_agent(ua: str) -> dict:
    ua = ua or ""
    lowered = ua.lower()
    device_type = "desktop"
    if "mobile" in lowered or "android" in lowered and "mobile" in lowered:
        device_type = "mobile"
    elif "tablet" in lowered or "ipad" in lowered:
        device_type = "tablet"
    elif "curl" in lowered or "wget" in lowered or "python-requests" in lowered or "postman" in lowered:
        device_type = "bot"

    # OS
    os_name = None
    if "iphone" in lowered or "ipad" in lowered or "ios" in lowered:
        os_name = "iOS"
    elif "windows" in lowered:
        os_name = "Windows"
    elif "mac os" in lowered or "macintosh" in lowered:
        os_name = "macOS"
    elif "android" in lowered:
        os_name = "Android"
    elif "linux" in lowered:
        os_name = "Linux"

    # Browser + version
    browser = "წვდომა API-ით" if device_type == "bot" else "ბრაუზერი"
    version = ""
    for name, pattern in (
        ("Chrome", r"chrome/(\d+)"),
        ("Firefox", r"firefox/(\d+)"),
        ("Safari", r"safari/(\d+)"),
        ("Edge", r"edg[ea]?/(\d+)"),
        ("Opera", r"opr/(\d+)"),
    ):
        m = re.search(pattern, lowered)
        if m and not (name == "Chrome" and "edg" in lowered):
            browser = name
            version = m.group(1)
            break
    # Edge fix: Edge UA contains Chrome too
    if "edg" in lowered and browser == "Chrome":
        browser = "Edge"
        m = re.search(r"edg/(\d+)", lowered)
        version = m.group(1) if m else version

    if device_type == "bot":
        if "curl" in lowered:
            browser = "curl"
        elif "python-requests" in lowered:
            browser = "Python requests"
        elif "postman" in lowered:
            browser = "Postman"

    if version:
        device_name = f"{browser} {version} — {os_name}" if os_name else f"{browser} {version}"
    else:
        device_name = f"{browser} — {os_name}" if os_name else browser
    return {
        "device_name": device_name,
        "os_name": os_name or None,
        "device_type": device_type,
    }
