from typing import Optional, List
from sqlalchemy import select
from ..models import User
from .base import BaseRepository

class UserRepository(BaseRepository):
    async def get_by_telegram_id(self, telegram_id: str) -> Optional[User]:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def get_active_admins(self) -> List[User]:
        result = await self.session.execute(
            select(User).where(User.is_admin == True, User.is_active == True)
        )
        return result.scalars().all()