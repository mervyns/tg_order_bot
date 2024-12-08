from typing import Optional
import logging
from datetime import datetime, timedelta
from supabase import create_client, Client

from forwarder import LOGGER

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _client: Optional[Client] = None
    _last_health_check: datetime = datetime.min
    _health_check_interval: timedelta = timedelta(minutes=5)

    def __init__(self, supabase_url: str, supabase_key: str, **kwargs):
        """Initialize Supabase client"""
        LOGGER.info("Initializing DatabaseManager with Supabase")
        
        if not supabase_url or not supabase_key:
            LOGGER.error("Supabase URL and key are required")
            raise ValueError("supabase_url and supabase_key are required")
            
        self._client = create_client(supabase_url, supabase_key)
        self._health_check_interval = timedelta(seconds=kwargs.get('health_check_interval', 300))
        
    @classmethod
    async def initialize(cls, supabase_url: str, supabase_key: str, **kwargs) -> 'DatabaseManager':
        """Initialize database manager as a singleton"""
        if not cls._instance:
            cls._instance = cls(supabase_url, supabase_key, **kwargs)
        return cls._instance
    
    @property
    def client(self) -> Client:
        """Get the Supabase client"""
        if not self._client:
            raise RuntimeError("Database client not initialized")
        return self._client
    
    async def check_health(self) -> bool:
        """Check database connection health"""
        try:
            # Simple health check query
            self._client.table('orders').select("count", count='exact').execute()
            self._last_health_check = datetime.now()
            return True
        except Exception as e:
            LOGGER.error(f"Health check failed: {e}")
            return False
            
    async def close(self):
        """Close the database connection"""
        # Supabase client doesn't require explicit closure
        self._client = None
        self._instance = None
        LOGGER.info("Database connection closed")