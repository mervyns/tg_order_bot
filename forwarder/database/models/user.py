from sqlalchemy import Column, Index, MetaData, String, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
import enum
from ..base import BaseModel

metadata = MetaData(schema='public')

class UserRole(enum.Enum):
    ADMIN = "admin"
    AGENT_MANAGER = "agent_manager"
    AGENT = "agent"
    CLIENT_MANAGER = "client_manager"
    CLIENT = "client"

class User(BaseModel):
    __tablename__ = 'users'

    telegram_id = Column(String(100), unique=True, nullable=False)
    username = Column(String(100))
    password = Column(String(100))
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.CLIENT)
    is_active = Column(Boolean, default=True)
    permissions = Column(JSONB, default={})
    settings = Column(JSONB, default={})

    # Relationships
    audit_logs = relationship("AuditLog", back_populates="user")

    # Indexes
    __table_args__ = (
        Index('idx_users_telegram_id_unique', 'telegram_id', unique=True),
        Index('idx_users_role_is_active', 'role', 'is_active'),
        {'schema': 'public', 'extend_existing': True}
    )

    def __repr__(self):
        return f"<User(telegram_id='{self.telegram_id}', role='{self.role.value}')>"
