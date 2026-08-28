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


def _ip_allowed(client_ip: str | None, allowed: list) -> bool:
    """Check client IP against exact IPs and CIDR ranges."""
    if not client_ip:
        return False
    import ipaddress
    for entry in allowed:
        try:
            if "/" in str(entry):
                if ipaddress.ip_address(client_ip) in ipaddress.ip_network(str(entry), strict=False):
                    return True
            elif client_ip == str(entry):
                return True
        except ValueError:
            continue
    return False


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
        # API P1.8: allowed IPs (exact or CIDR)
        client_ip = request.client.host if request.client else None
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        if key.allowed_ips:
            allowed = _ip_allowed(client_ip, key.allowed_ips)
            if not allowed:
                raise HTTPException(status_code=403, detail="IP არ არის დაშვებული ამ API გასაღებისთვის")
        # API P1.8: rate limit (sliding window per minute)
        now = datetime.utcnow()
        if key.rate_window_start and (now - key.rate_window_start).total_seconds() < 60:
            if key.rate_window_count >= key.rate_limit_per_minute:
                raise HTTPException(status_code=429, detail="Rate limit გადაჭარბებულია")
            key.rate_window_count += 1
        else:
            key.rate_window_start = now
            key.rate_window_count = 1
        user = (await db.execute(select(User).where(User.id == key.user_id))).scalar_one_or_none()
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="მომხმარებელი არ მოიძებნა ან დეაქტივირებულია")
        key.last_used_at = now
        await db.flush()
        await db.execute(
            text("SELECT set_config('app.current_company_id', :cid, true)"),
            {"cid": str(user.company_id)},
        )
        current_company_id.set(user.company_id)
        # Expose the key's scopes for require_module enforcement (Odoo access rights)
        request.state.api_key_scopes = [s.strip() for s in key.scopes.split(",") if s.strip()]
        request.state.api_key_branch_id = key.branch_id
        request.state.api_key_resource_ids = key.resource_ids or []
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
        request: Request,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user_or_api_key),
    ) -> User:
        # API key scope enforcement (Odoo access rights): module[.action] must be in scopes
        scopes = getattr(request.state, "api_key_scopes", None)
        if scopes is not None and "*" not in scopes:
            # map permission → action for granular scope matching (sales.read, inventory.write)
            action_map = {"can_access": "read", "can_view": "read", "can_create": "write", "can_edit": "write", "can_delete": "admin"}
            action = action_map.get(permission, "read")
            module_ok = module_code in scopes
            granular_ok = any(
                s == f"{module_code}.{action}" or s == f"{module_code}.read" and action == "read"
                for s in scopes
            )
            if not (module_ok or granular_ok):
                raise HTTPException(status_code=403, detail=f"API გასაღებს არ აქვს წვდომა მოდულზე: {module_code}.{action}")

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
