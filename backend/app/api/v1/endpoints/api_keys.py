"""API keys endpoints — Odoo JSON-2 API style: create/list/revoke/rotate + bot users."""
import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.core.security import hash_password
from app.models.integration import ApiKey
from app.models.user import User
from app.schemas.common import ResponseBase

router = APIRouter(prefix="/api-keys", tags=["API Keys"])


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_key() -> tuple[str, str]:
    """Returns (raw_key, prefix). Raw key shown only once."""
    raw = f"bos_{secrets.token_hex(24)}"
    return raw, raw[:12]


@router.get("/", response_model=ResponseBase[list[dict]])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = (await db.execute(
        select(ApiKey).where(ApiKey.company_id == current_user.company_id).order_by(ApiKey.created_at.desc())
    )).scalars().all()
    return ResponseBase(data=[{
        "id": str(k.id), "name": k.name, "key_prefix": k.key_prefix,
        "scopes": k.scopes, "expires_at": k.expires_at.isoformat() if k.expires_at else None,
        "last_used_at": k.last_used_at.isoformat() if k.last_used_at else None,
        "is_active": k.is_active, "created_at": k.created_at.isoformat(),
        "user_id": str(k.user_id),
    } for k in rows])


@router.post("/", response_model=ResponseBase[dict], status_code=201)
async def create_api_key(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create an API key. Returns the raw key ONCE — store it securely."""
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="გასაღების სახელი სავალდებულოა")
    scopes = payload.get("scopes") or "*"
    ttl_days = int(payload.get("ttl_days") or 365)
    raw, prefix = _generate_key()
    key = ApiKey(
        company_id=current_user.company_id,
        user_id=current_user.id,
        name=name,
        key_hash=_hash_key(raw),
        key_prefix=prefix,
        scopes=scopes,
        expires_at=datetime.utcnow() + timedelta(days=ttl_days),
    )
    db.add(key)
    await db.flush()
    return ResponseBase(data={
        "id": str(key.id), "name": key.name, "key": raw,  # shown once
        "key_prefix": prefix, "scopes": scopes,
        "expires_at": key.expires_at.isoformat() if key.expires_at else None,
    }, message="API გასაღები შეიქმნა — შეინახე, მეორედ არ გაჩვენდება")


@router.post("/{key_id}/rotate", response_model=ResponseBase[dict])
async def rotate_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Rotate: revoke the old key, issue a new one (Odoo rotation)."""
    key = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="გასაღები არ მოიძებნა")
    raw, prefix = _generate_key()
    new_key = ApiKey(
        company_id=current_user.company_id,
        user_id=key.user_id,
        name=f"{key.name} (rotated)",
        key_hash=_hash_key(raw),
        key_prefix=prefix,
        scopes=key.scopes,
        expires_at=key.expires_at,
        rotated_from_id=key.id,
    )
    key.is_active = False
    db.add(new_key)
    await db.flush()
    return ResponseBase(data={
        "id": str(new_key.id), "key": raw, "key_prefix": prefix,
        "scopes": new_key.scopes, "expires_at": new_key.expires_at.isoformat() if new_key.expires_at else None,
    }, message="გასაღები როტირებულია — ძველი გაუქმდა")


@router.post("/{key_id}/revoke", response_model=ResponseBase)
async def revoke_api_key(
    key_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    key = (await db.execute(
        select(ApiKey).where(ApiKey.id == key_id, ApiKey.company_id == current_user.company_id)
    )).scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="გასაღები არ მოიძებნა")
    key.is_active = False
    await db.flush()
    return ResponseBase(message="გასაღები გაუქმდა")


@router.post("/bot-users", response_model=ResponseBase[dict], status_code=201)
async def create_bot_user(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Create a dedicated bot user (no interactive login) for API access."""
    email = (payload.get("email") or "").strip().lower()
    name = (payload.get("name") or "").strip()
    if not email or not name:
        raise HTTPException(status_code=400, detail="ელ.ფოსტა და სახელი სავალდებულოა")
    existing = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="მომხმარებელი ამ ელ.ფოსტით უკვე არსებობს")
    bot = User(
        company_id=current_user.company_id,
        email=email,
        hashed_password=hash_password(secrets.token_urlsafe(32)),  # unusable password
        full_name=name,
        role="employee",
        is_active=True,
    )
    db.add(bot)
    await db.flush()
    return ResponseBase(data={"id": str(bot.id), "email": bot.email, "name": bot.full_name},
                        message="Bot მომხმარებელი შეიქმნა")
