from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.security import get_current_user
from app.models.user import User


async def get_db_session(db: AsyncSession = Depends(get_db)) -> AsyncSession:
    return db


CommonUser = Depends(get_current_user)
