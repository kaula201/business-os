"""RFC 6238 TOTP (SHA-1, 30s, 6 digits) without an extra dependency."""
import base64
import hashlib
import hmac
import secrets
import struct
import time


def generate_totp_secret() -> str:
    """Base32 secret suitable for authenticator apps (no padding)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    padded = secret.strip().upper().replace(" ", "")
    padded += "=" * ((8 - len(padded) % 8) % 8)
    return base64.b32decode(padded, casefold=True)


def totp_at(secret: str, timestamp: int) -> str:
    key = _decode_secret(secret)
    counter = int(timestamp) // 30
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{binary % 1_000_000:06d}"


def current_totp(secret: str, now: int | None = None) -> str:
    return totp_at(secret, int(time.time() if now is None else now))


def verify_totp(secret: str, code: str, *, window: int = 1, now: int | None = None) -> bool:
    """Accept the current step and `window` steps of clock skew."""
    candidate = (code or "").strip().replace(" ", "")
    if len(candidate) != 6 or not candidate.isdigit():
        return False
    try:
        _decode_secret(secret)
    except Exception:
        return False
    moment = int(time.time() if now is None else now)
    for offset in range(-window, window + 1):
        expected = totp_at(secret, moment + offset * 30)
        if hmac.compare_digest(expected, candidate):
            return True
    return False
