# backend/app/api/v1/endpoints/auth.py
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.time import utc_now
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.models.company import Company
from app.models.security import LoginHistory, User2FA
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, UserUpdate, UserInvite
from app.schemas.common import ResponseBase, MessageResponse
from app.core.config import settings
from app.core.dependencies import get_current_user
import uuid
from jose import jwt
from datetime import datetime, timedelta

router = APIRouter(prefix="/auth", tags=["ავტორიზაცია"])


class SSOTokenResponse(BaseModel):
    token: str
    expires_in: int = 300


@router.get("/sso-token", response_model=ResponseBase[SSOTokenResponse])
async def get_sso_token(current_user: User = Depends(get_current_user)):
    """Issue a short-lived cross-app SSO token for CRM OS.

    Signed with the same JWT_SECRET_KEY (HS256) that CRM OS trusts.
    Payload carries the user's email + name + type='sso'; expires in 5 minutes.
    """
    expire = utc_now() + timedelta(minutes=5)
    payload = {
        "sub": str(current_user.id),
        "email": current_user.email,
        "full_name": current_user.full_name,
        "type": "sso",
        "exp": expire,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return ResponseBase(data=SSOTokenResponse(token=token))


@router.post("/register", response_model=ResponseBase[TokenResponse])
async def register(data: UserCreate, db: AsyncSession = Depends(get_db)):
    # შემოწმება: email უნიკალურია
    result = await db.execute(select(User).where(User.email == data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ელფოსტა უკვე რეგისტრირებულია")

    # კომპანიის შექმნა
    company = Company(
        name=data.company_name,
        identification_code=f"COMP-{uuid.uuid4().hex[:8].upper()}",
        vat_status=data.is_vat_payer,
        currency="GEL"
    )
    db.add(company)
    await db.flush()

    # მომხმარებლის შექმნა (ადმინისტრატორი)
    user = User(
        company_id=company.id,
        email=data.email,
        hashed_password=hash_password(data.password),
        full_name=data.full_name,
        role=User.Role.ADMIN,
        is_active=True,
        email_verified=False,
        email_verification_token=create_access_token(
            {"sub": str(uuid.uuid4()), "type": "email_verify"},
            expires_delta=timedelta(days=7),
        ),
    )
    db.add(user)
    await db.flush()

    # Token-ები
    token_data = {"sub": str(user.id), "company_id": str(company.id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return ResponseBase(data=TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    ))


@router.post("/login", response_model=ResponseBase[TokenResponse])
async def login(data: UserLogin, request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="არასწორი ელფოსტა ან პაროლი")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="ანგარიში დეაქტივირებულია")

    # ბოლო შესვლის განახლება
    from datetime import datetime
    user.last_login = utc_now()

    # Login history ჩაწერა — IP + device (user-agent)
    client_ip = request.client.host if request.client else None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    user_agent = request.headers.get("user-agent")
    db.add(LoginHistory(
        user_id=user.id,
        company_id=user.company_id,
        ip_address=client_ip,
        user_agent=(user_agent or "")[:255],
        success=True,
    ))

    token_data = {"sub": str(user.id), "company_id": str(user.company_id), "role": user.role}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    return ResponseBase(data=TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserResponse.model_validate(user)
    ))


@router.post("/refresh", response_model=ResponseBase[TokenResponse])
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    from app.core.security import decode_token
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="არასწორი refresh token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="მომხმარებელი არ მოიძებნა")

    token_data = {"sub": str(user.id), "company_id": str(user.company_id), "role": user.role}
    new_access_token = create_access_token(token_data)
    new_refresh_token = create_refresh_token(token_data)

    return ResponseBase(data=TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        user=UserResponse.model_validate(user)
    ))


# ── Password Reset ────────────────────────────────────────────────────────────


@router.post("/forgot-password", response_model=ResponseBase[MessageResponse])
async def forgot_password(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Generate a password-reset token. In production this would be emailed."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        # Don't reveal whether the email exists
        return ResponseBase(data=MessageResponse(message="თუ ელფოსტა რეგისტრირებულია, პაროლის აღდგენის ინსტრუქცია გამოგეგზავნებათ"))

    token_data = {"sub": str(user.id), "type": "password_reset"}
    reset_token = create_access_token(token_data, expires_delta=timedelta(hours=1))

    # In production: send email with reset link
    # For now: return the token directly (dev convenience)
    return ResponseBase(data=MessageResponse(
        message="თუ ელფოსტა რეგისტრირებულია, პაროლის აღდგენის ინსტრუქცია გამოგეგზავნებათ"
    ))


@router.post("/reset-password", response_model=ResponseBase[MessageResponse])
async def reset_password(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using a valid reset token."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "password_reset":
        raise HTTPException(status_code=400, detail="არასწორი ან ვადაგასული token")

    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი არ მოიძებნა")

    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="პაროლი უნდა შეიცავდეს მინიმუმ 8 სიმბოლოს")

    user.hashed_password = hash_password(new_password)
    await db.flush()

    return ResponseBase(data=MessageResponse(message="პაროლი წარმატებით შეიცვალა"))


# ── Email Verification ────────────────────────────────────────────────────────


@router.get("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify email address using a verification token."""
    payload = decode_token(token)
    if not payload or payload.get("type") != "email_verify":
        raise HTTPException(status_code=400, detail="არასწორი ან ვადაგასული verification token")

    result = await db.execute(
        select(User).where(User.email_verification_token == token)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი არ მოიძებნა")

    if user.email_verified:
        return ResponseBase(data=MessageResponse(message="ელფოსტა უკვე დადასტურებულია"))

    user.email_verified = True
    user.email_verification_token = None
    await db.flush()

    return ResponseBase(data=MessageResponse(message="ელფოსტა წარმატებით დადასტურდა"))


@router.post("/resend-verification", response_model=ResponseBase[MessageResponse])
async def resend_verification(
    data: UserLogin,
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification token."""
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()
    if not user:
        return ResponseBase(data=MessageResponse(message="თუ ელფოსტა რეგისტრირებულია, verification ბმული გამოგეგზავნებათ"))

    if user.email_verified:
        return ResponseBase(data=MessageResponse(message="ელფოსტა უკვე დადასტურებულია"))

    user.email_verification_token = create_access_token(
        {"sub": str(uuid.uuid4()), "type": "email_verify"},
        expires_delta=timedelta(days=7),
    )
    await db.flush()

    return ResponseBase(data=MessageResponse(message="თუ ელფოსტა რეგისტრირებულია, verification ბმული გამოგეგზავნებათ"))


# ── 2FA ────────────────────────────────────────────────────────────────────────

@router.get("/2fa/status", response_model=ResponseBase[dict])
async def two_fa_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User2FA).where(User2FA.user_id == current_user.id))
    record = result.scalar_one_or_none()
    return ResponseBase(data={"enabled": bool(record and record.is_enabled)})


@router.post("/2fa/setup", response_model=ResponseBase[dict])
async def two_fa_setup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Generate a TOTP secret for the user (sandbox: returns the secret to display)."""
    import secrets as _secrets
    secret = _secrets.token_hex(20)
    result = await db.execute(select(User2FA).where(User2FA.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if record:
        record.secret = secret
        record.is_enabled = True
    else:
        db.add(User2FA(user_id=current_user.id, secret=secret, is_enabled=True))
    await db.commit()
    return ResponseBase(data={"secret": secret, "enabled": True}, message="2FA ჩართულია")


@router.post("/2fa/disable", response_model=ResponseBase[dict])
async def two_fa_disable(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(User2FA).where(User2FA.user_id == current_user.id))
    record = result.scalar_one_or_none()
    if record:
        record.is_enabled = False
        await db.commit()
    return ResponseBase(data={"enabled": False}, message="2FA გამორთულია")


# ── Login history ──────────────────────────────────────────────────────────────

@router.get("/login-history", response_model=ResponseBase[list[dict]])
async def login_history(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(LoginHistory).where(LoginHistory.user_id == current_user.id).order_by(LoginHistory.created_at.desc()).limit(50)
    )
    return ResponseBase(data=[{
        "id": str(h.id), "ip_address": h.ip_address, "user_agent": h.user_agent,
        "success": h.success, "created_at": h.created_at.isoformat(),
    } for h in result.scalars().all()])
