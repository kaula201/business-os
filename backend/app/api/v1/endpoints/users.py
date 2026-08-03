# backend/app/api/v1/endpoints/users.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from uuid import UUID
from app.core.database import get_db
from app.core.security import hash_password
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate, UserInvite
from app.schemas.common import ResponseBase, PaginatedResponse

router = APIRouter(prefix="/users", tags=["მომხმარებლები"])


@router.get("/", response_model=ResponseBase[PaginatedResponse[UserResponse]])
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: Optional[str] = None,
    is_active: Optional[bool] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(User).where(User.company_id == current_user.company_id)

    if role:
        query = query.where(User.role == role)
    if is_active is not None:
        query = query.where(User.is_active == is_active)
    if search:
        query = query.where(
            User.full_name.ilike(f"%{search}%") | User.email.ilike(f"%{search}%")
        )

    # სულ რაოდენობა
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    # პაგინაცია
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    users = result.scalars().all()

    return ResponseBase(data=PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size
    ))


@router.get("/me", response_model=ResponseBase[UserResponse])
async def get_me(current_user: User = Depends(get_current_user)):
    return ResponseBase(data=UserResponse.model_validate(current_user))


@router.get("/{user_id}", response_model=ResponseBase[UserResponse])
async def get_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.company_id == current_user.company_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი არ მოიძებნა")
    return ResponseBase(data=UserResponse.model_validate(user))


@router.patch("/{user_id}", response_model=ResponseBase[UserResponse])
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role not in [User.Role.ADMIN]:
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    result = await db.execute(
        select(User).where(User.id == user_id, User.company_id == current_user.company_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი არ მოიძებნა")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    return ResponseBase(data=UserResponse.model_validate(user))


@router.delete("/{user_id}", response_model=ResponseBase[dict])
async def deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="წვდომა აკრძალულია")

    result = await db.execute(
        select(User).where(User.id == user_id, User.company_id == current_user.company_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="მომხმარებელი არ მოიძებნა")

    user.is_active = False
    await db.flush()
    from app.api.v1.endpoints.purchase_orders import add_audit
    add_audit(db, current_user, "user.deactivated", "user", user.id, {
        "email": user.email, "role": user.role,
    })
    return ResponseBase(data=dict(message="მომხმარებელი დეაქტივირებულია"))


# ── User Invite ────────────────────────────────────────────────────────────────


@router.post("/invite", response_model=ResponseBase[UserResponse])
async def invite_user(
    data: UserInvite,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Invite a new user to the company (admin only)."""
    if current_user.role != User.Role.ADMIN:
        raise HTTPException(status_code=403, detail="მხოლოდ ადმინისტრატორს შეუძლია მომხმარებლის მოწვევა")

    # Check email uniqueness
    existing = await db.execute(select(User).where(User.email == data.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="ელფოსტა უკვე რეგისტრირებულია")

    # Generate a random temporary password
    import secrets, string
    temp_password = secrets.token_urlsafe(12)

    user = User(
        company_id=current_user.company_id,
        email=data.email,
        hashed_password=hash_password(temp_password),
        full_name=data.full_name.strip(),
        role=data.role,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # In production: send email with temp password
    return ResponseBase(data=UserResponse.model_validate(user))


# ── Change Password ────────────────────────────────────────────────────────────


from pydantic import BaseModel, Field


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)


@router.post("/change-password", response_model=ResponseBase[dict])
async def change_password(
    data: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Change the current user's password."""
    from app.core.security import verify_password

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="მიმდინარე პაროლი არასწორია")

    current_user.hashed_password = hash_password(data.new_password)
    await db.flush()
    return ResponseBase(data=dict(message="პაროლი წარმატებით შეიცვალა"))
