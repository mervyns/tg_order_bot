from sqlalchemy import (
    Column, String, Numeric, Text, MetaData, Enum as SQLEnum,
    Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
import enum
from ..base import BaseModel

metadata = MetaData(schema='public')

class OrderStatus(enum.Enum):
    PENDING = "pending"
    BANK_PROCESSING = "bank_processing"
    CREATED = "created"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    REFUND_PENDING = "refund_pending"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"
    CREDITED = "credited"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"

class Order(BaseModel):
    __tablename__ = 'orders'

    order_ref = Column(String(50), nullable=False)
    swift_code = Column(String(50))
    bank_name = Column(String(255))
    bank_country = Column(String(100))
    account_number = Column(String(100))
    beneficiary_name = Column(String(255))
    currency = Column(String(10))
    amount = Column(Numeric(precision=15, scale=2))
    agent_code = Column(String(10))
    client_code = Column(String(10))
    payout_company = Column(String(255))
    rate = Column(Numeric(precision=6, scale=4))
    validation_messages = Column(Text)
    status = Column(SQLEnum(OrderStatus), nullable=False, default=OrderStatus.PENDING)
    order_metadata = Column(JSONB, default={})

    # Foreign keys
    created_by_id = Column(String(50))
    updated_by_id = Column(String(50))

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="order")

    # Indexes and constraints
    __table_args__ = (
        Index('idx_orders_order_ref', 'order_ref'),
        Index('idx_orders_status', 'status'),
        Index('idx_orders_created_at', 'created_at'),
        CheckConstraint('amount > 0', name='check_amount_positive'),
        Index('idx_orders_status_created_at', 'status', 'created_at'),
        Index('idx_orders_beneficiary_name', 'beneficiary_name'),
        {'schema': 'public', 'extend_existing': True}
    )

    def __repr__(self):
        return f"<Order(order_ref='{self.order_ref}', status='{self.status}')>"
