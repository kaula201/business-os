# backend/app/core/dependencies.py
import hashlib
from datetime import datetime
from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from app.core.database import get_db, current_company_id
from app.core.security import decode_token
from app.models.user import User
from app.models.module import AppModule, ModulePermission
from app.models.integration import ApiKey


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="ავტორიზაცია არ არის მოწოდებული")

    token = auth_header.split(" ")[1]
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="არასწორი ან ვადაგასული token")

    user_id = payload.get("sub")
    # Keep as string for SQLite compatibility (PostgreSQL UUID works with string comparison)
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="მომხმარებელი არ მოიძებნა ან დეაქტივირებულია")

    # Row-Level Security: pin the tenant for this request's DB transaction.
    # set_config(..., is_local=true) is the parameterized equivalent of
    # SET LOCAL: it resets at transaction end, so pooled connections can
    # never leak another company's scope.
    await db.execute(
        text("SELECT set_config('app.current_company_id', :cid, true)"),
        {"cid": str(user.company_id)},
    )
    current_company_id.set(user.company_id)

    return user


async def get_current_user_or_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Accept either a Bearer JWT or an X-API-Key (Odoo JSON-2 API style).

    API keys: SHA-256 hash lookup, expiration check, last_used_at update.
    """
    api_key = request.headers.get("X-API-Key")
    if api_key:
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        key = (await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash))).scalar_one_or_none()
        if not key or not key.is_active:
            raise HTTPException(status_code=401, detail="არასწორი ან გაუქმებული API გასაღები")
        if key.expires_at and key.expires_at < datetime.utcnow():
            raise HTTPException(status_code=401, detail="API გასაღების ვადა გასულია")
        user = (await db.execute(select(User).where(User.id == key.user_id))).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="მომხმარებელი არ მოიძებნა ან დეაქტივირებულია")
        key.last_used_at = datetime.utcnow()
        await db.flush()
        await db.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": str(user.company_id)},
        )
        current_company_id.set(user.company_id)
        return user
    return await get_current_user(request, db)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="მხოლოდ ადმინისტრატორს შეუძლია")
    return current_user


def require_any_role(
    current_user: User,
    *allowed_roles: User.Role,
    detail: str = "ამ მოქმედების უფლება არ გაქვთ",
) -> None:
    """Coarse backend authorization guard used until module permissions land."""
    if current_user.role not in allowed_roles:
        raise HTTPException(status_code=403, detail=detail)


def require_module(module_code: str, permission: str = "can_access"):
    """Factory: returns a FastAPI dependency that checks module-level permission.

    Usage in endpoint:
        current_user: User = Depends(require_module("cash", "can_create"))
    """
    async def _check(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user_or_api_key),
    ) -> User:
        # Admin always has full access
        if current_user.role == User.Role.ADMIN:
            return current_user

        # Find the module
        mod_result = await db.execute(
            select(AppModule).where(AppModule.code == module_code, AppModule.is_active == True)
        )
        module = mod_result.scalar_one_or_none()
        if not module:
            raise HTTPException(status_code=403, detail="მოდული არ არის რეგისტრირებული")

        # Check if company has this module enabled
        from app.models.module import CompanyModule
        cm_result = await db.execute(
            select(CompanyModule).where(
                CompanyModule.company_id == current_user.company_id,
                CompanyModule.module_id == module.id,
                CompanyModule.enabled == True,
            )
        )
        if not cm_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="მოდული გამორთულია კომპანიისთვის")

        # Check permission for this role
        perm_result = await db.execute(
            select(ModulePermission).where(
                ModulePermission.module_id == module.id,
                ModulePermission.role == current_user.role,
            )
        )
        perm = perm_result.scalar_one_or_none()

        if perm:
            allowed = getattr(perm, permission, False)
            if not allowed:
                raise HTTPException(status_code=403, detail="ამ მოქმედების უფლება არ გაქვთ")
        else:
            # No explicit permission row — employee can only access
            if permission != "can_access" and current_user.role == User.Role.EMPLOYEE:
                raise HTTPException(status_code=403, detail="ამ მოქმედების უფლება არ გაქვთ")

        return current_user

    return _check
