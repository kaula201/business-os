# backend/app/security.py
"""Legacy compatibility module — delegates to app.core.security.

Kept for generator scripts that import from `app.security`. The live
application imports from `app.core.security`.
"""
from app.core.security import (  # noqa: F401
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
