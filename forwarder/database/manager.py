from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from contextlib import asynccontextmanager
import logging
from datetime import datetime, timedelta
from typing import Optional, AsyncGenerator

from forwarder import LOGGER

logger = logging.getLogger(__name__)

class DatabaseManager:
    _instance: Optional['DatabaseManager'] = None
    _engine = None
    _session_maker = None
    _last_health_check: datetime = datetime.min
    _health_check_interval: timedelta = timedelta(minutes=5)

    def __init__(self, database_url: str, **kwargs):
        """Initialize database manager"""
        LOGGER.info("Initializing DatabaseManager")
        
        if not database_url:
            LOGGER.error("No database_url provided")
            raise ValueError("database_url is required")
            
        LOGGER.info(f"Original database URL type: {database_url.split('://')[0] if '://' in database_url else 'unknown'}")
        
        # Standardize the URL format - ensure we're using asyncpg
        if 'postgresql+psycopg2' in database_url:
            LOGGER.info("Converting psycopg2 URL to asyncpg")
            database_url = database_url.replace('postgresql+psycopg2', 'postgresql+asyncpg')
        elif 'postgresql://' in database_url:
            LOGGER.info("Adding asyncpg dialect to URL")
            database_url = database_url.replace('postgresql://', 'postgresql+asyncpg://')
            
        LOGGER.info(f"Final database URL type: {database_url.split('://')[0] if '://' in database_url else 'unknown'}")
        
        # Default configuration
        self.config = {
            'pool_size': kwargs.get('pool_size', 32),  
            'max_overflow': kwargs.get('max_overflow', 64),  
            'pool_timeout': kwargs.get('pool_timeout', 10),  
            'pool_recycle': kwargs.get('pool_recycle', 3600),  
            'pool_pre_ping': True,  
            'health_check_interval': kwargs.get('health_check_interval', 300)
        }
        
        try:
            self._engine = create_async_engine(
                database_url,
                pool_size=self.config['pool_size'],
                max_overflow=self.config['max_overflow'],
                pool_timeout=self.config['pool_timeout'],
                pool_recycle=self.config['pool_recycle'],
                pool_pre_ping=self.config['pool_pre_ping'],  
                echo=False  
            )
            
            self._session_maker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autocommit=False,
                autoflush=False
            )
            
            LOGGER.info("Database engine created successfully")
        except Exception as e:
            LOGGER.error(f"Failed to create database engine: {e}")
            raise

    @classmethod
    async def initialize(cls, **kwargs) -> 'DatabaseManager':
        """Initialize the database manager singleton"""
        logger.info(f"Initializing DatabaseManager with kwargs: {', '.join(kwargs.keys())}")
        
        # Log all configuration values (masking sensitive data)
        for key, value in kwargs.items():
            if isinstance(value, str) and ('password' in key.lower() or 'url' in key.lower()):
                if key == 'database_url' and value:
                    try:
                        parts = value.split('@')
                        if len(parts) > 1:
                            logger.info(f"  {key}: {value}")
                        else:
                            logger.info(f"  {key}: <malformed_url>")
                    except Exception as e:
                        logger.error(f"Error parsing database URL for logging: {e}")
                else:
                    logger.info(f"  {key}: ****")
            else:
                logger.info(f"  {key}: {value}")
        
        if 'database_url' not in kwargs:
            logger.error("No database_url provided in kwargs")
            raise ValueError("database_url is required")
            
        if cls._instance is None:
            try:
                cls._instance = cls(**kwargs)
                logger.info("DatabaseManager instance created")
                
                # Test connection
                async with cls._instance._engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))
                logger.info("Database connection test successful")
            except Exception as e:
                logger.error(f"Database connection test failed: {e}")
                cls._instance = None
                raise
        return cls._instance

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a database session using async context manager"""
        if not self._session_maker:
            raise RuntimeError("DatabaseManager not initialized")

        session = self._session_maker()
        try:
            yield session
        except Exception as e:
            logger.error(f"Session error: {e}")
            await session.rollback()
            raise
        finally:
            await session.close()

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """Get a session with transaction management"""
        async with self.get_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def check_health(self) -> bool:
        """Check database connection health"""
        try:
            logger.info("Performing database health check")
            async with self.get_session() as session:
                result = await session.execute(text("SELECT 1"))
                await result.scalar()
                self._last_health_check = datetime.utcnow()
                logger.info("Database health check successful")
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False

    async def close(self) -> None:
        """Close all database connections"""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")

    async def get_pool_status(self) -> dict:
        """Get database connection pool status"""
        if not self._engine:
            return {"error": "Engine not initialized"}
        
        return {
            "size": self._engine.pool.size(),
            "checked_in": self._engine.pool.checkedin(),
            "checked_out": self._engine.pool.checkedout(),
            "overflow": self._engine.pool.overflow(),
        }