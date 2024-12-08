from datetime import datetime
import uuid
from typing import Dict, Any

class BaseModel:
    """Base model for Supabase tables"""
    
    def __init__(self, **kwargs):
        self.id: str = kwargs.get('id', str(uuid.uuid4()))
        self.created_at: datetime = kwargs.get('created_at', datetime.utcnow())
        self.updated_at: datetime = kwargs.get('updated_at', datetime.utcnow())
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for Supabase"""
        return {
            'id': self.id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """Create model instance from Supabase data"""
        if 'created_at' in data:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)
