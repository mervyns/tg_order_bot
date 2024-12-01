from sqlalchemy import Column, Index, String, Text, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from ..base import BaseModel
from .user import User
from .order import Order

class AuditLog(BaseModel):
    __tablename__ = 'audit_logs'

    action = Column(String(100), nullable=False)
    details = Column(Text)
    order_id = Column(UUID(as_uuid=True), ForeignKey('public.orders.id'))
    user_id = Column(UUID(as_uuid=True), ForeignKey('public.users.id'))

    # Relationships
    order = relationship("Order", back_populates="audit_logs")
    user = relationship("User", back_populates="audit_logs")

    # Indexes
    __table_args__ = (
        Index('idx_audit_logs_action', 'action'),
        Index('idx_audit_logs_created_at', 'created_at'),
        Index('idx_audit_logs_order_id', 'order_id'),
        {'schema': 'public'}
    )

    def __repr__(self):
        return f"<AuditLog(action='{self.action}', order_id={self.order_id})>"
