from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, text
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime

Base = declarative_base()

class BaseModel(Base):
    """Abstract base model with common fields"""
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=text('NOW()'), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text('NOW()'), onupdate=datetime.utcnow, nullable=False)
