# forwarder/modules/initialize.py
import asyncio
from typing import Optional
from forwarder import LOGGER
from forwarder.database.manager import DatabaseManager
from forwarder.config.config_manager import get_config

# Initialize configuration manager
config_manager = get_config()

# Global database manager instance - this is what other modules will import
db_manager: Optional[DatabaseManager] = None

async def get_db_manager() -> Optional[DatabaseManager]:
    """Get the database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = await init_db()
    return db_manager

async def init_db() -> Optional[DatabaseManager]:
    """Initialize database connection"""
    global db_manager
    try:
        LOGGER.info("Getting database configuration...")
        db_config = config_manager.get_database_config()
        if not db_config:
            LOGGER.error("Failed to get database configuration")
            return None
            
        LOGGER.info("Initializing database manager...")
        db_manager = await DatabaseManager.initialize(**db_config)
        return db_manager
    except Exception as e:
        LOGGER.error(f"Database initialization failed: {e}")
        return None

async def initialize() -> Optional[DatabaseManager]:
    """Main initialization function"""
    global db_manager
    try:
        LOGGER.info("Starting database initialization...")
        db_manager = await init_db()
        if not db_manager:
            raise Exception("Failed to initialize database manager")
        LOGGER.info("Database initialization completed successfully")
        return db_manager
    except Exception as e:
        LOGGER.error(f"Initialization failed: {e}")
        raise

# Create sync getter for compatibility
async def get_initialized_db() -> Optional[DatabaseManager]:
    """Get the initialized database manager instance"""
    global db_manager
    if db_manager is None:
        db_manager = await init_db()
    return db_manager

# Export these for other modules
__all__ = ['db_manager', 'get_db_manager', 'initialize', 'get_initialized_db']

# Only execute if run directly
if __name__ == "__main__":
    asyncio.run(initialize())