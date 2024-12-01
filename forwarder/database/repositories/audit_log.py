from typing import Optional, List
from sqlalchemy import select
from ..models import AuditLog
from .base import BaseRepository

class AuditLogRepository(BaseRepository):
    async def create_log(
        self,
        action: str,
        details: str,
        user_id: Optional[int] = None,
        order_id: Optional[int] = None
    ) -> AuditLog:
        return await self.create(
            AuditLog,
            action=action,
            details=details,
            user_id=user_id,
            order_id=order_id
        )

    async def get_logs_by_order(self, order_id: int) -> List[AuditLog]:
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.order_id == order_id)
            .order_by(AuditLog.created_at.desc())
        )
        return result.scalars().all()
