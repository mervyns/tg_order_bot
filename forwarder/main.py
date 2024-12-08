import asyncio
import importlib
import sys
import signal
from forwarder import LOGGER, get_bot
from forwarder.modules import ALL_MODULES
from forwarder.modules.initialize import initialize, get_db_manager
from telegram import Update
from typing import Optional

class BotManager:
    def __init__(self):
        self.bot = None
        self.health_check_task: Optional[asyncio.Task] = None
        self.shutdown_event = asyncio.Event()
        
    async def cleanup(self):
        """Cleanup resources"""
        try:
            # Cancel health check task if running
            if self.health_check_task and not self.health_check_task.done():
                self.health_check_task.cancel()
                try:
                    await self.health_check_task
                except asyncio.CancelledError:
                    pass

            # Stop the bot if running
            if self.bot and self.bot.running:
                if self.bot.updater.running:
                    await self.bot.updater.stop()
                await self.bot.stop()

            # Cleanup database
            db_manager = await get_db_manager()
            if db_manager:
                await db_manager.close()
                LOGGER.info("Database connection closed")

        except Exception as e:
            LOGGER.error(f"Error during cleanup: {e}")

    async def initialize_app(self):
        """Initialize all required components"""
        try:
            # Initialize database first
            LOGGER.info("Initializing database...")
            db_manager = await initialize()
            if not db_manager:
                LOGGER.error("Failed to initialize database")
                return False

            # Initialize bot only once
            if not self.bot:
                LOGGER.info("Initializing bot...")
                self.bot = get_bot()
                await self.bot.initialize()

            # Load all modules
            LOGGER.info("Loading modules...")
            for module in ALL_MODULES:
                importlib.import_module("forwarder.modules." + module)
            
            LOGGER.info("Successfully loaded modules: " + str(ALL_MODULES))
            
            # Register handlers
            LOGGER.info("Registering handlers...")
            from forwarder.modules.message_handler import register_handlers as register_message_handlers
            from forwarder.modules.document_handler import register_handlers as register_document_handlers
            from forwarder.modules.default import register_handlers as register_default_handlers
            from forwarder.modules.misc import register_handlers as register_misc_handlers
            
            register_message_handlers()
            register_document_handlers()
            register_default_handlers()
            register_misc_handlers()
            
            return True
            
        except Exception as e:
            LOGGER.error(f"Initialization failed: {e}")
            return False

    async def health_check(self, start_time: float):
        """Perform periodic health checks"""
        last_check_time = asyncio.get_event_loop().time()
        check_count = 0
        
        while not self.shutdown_event.is_set():
            try:
                current_time = asyncio.get_event_loop().time()
                uptime = current_time - start_time
                time_since_last_check = current_time - last_check_time
                
                # Test bot connection
                try:
                    me = await asyncio.wait_for(self.bot.bot.get_me(), timeout=10)
                    connection_status = "Connected"
                except Exception as e:
                    connection_status = f"Disconnected: {str(e)}"
                    LOGGER.error(f"Connection test failed: {e}")
                
                LOGGER.info(
                    f"Health check #{check_count} - "
                    f"Uptime: {uptime:.2f}s, "
                    f"Time since last check: {time_since_last_check:.2f}s, "
                    f"Status: {connection_status}"
                )
                
                last_check_time = current_time
                check_count += 1
                
                if not self.bot.updater.running or connection_status != "Connected":
                    LOGGER.warning("Potential issues detected - initiating shutdown")
                    self.shutdown_event.set()
                    break
                
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                LOGGER.info("Health check cancelled")
                break
            except Exception as e:
                LOGGER.error(f"Health check failed: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def run(self):
        """Main run method"""
        start_time = asyncio.get_event_loop().time()
        
        try:
            LOGGER.info("=== Starting bot application ===")
            
            if not await self.initialize_app():
                LOGGER.error("Initialization failed, exiting application")
                return
            
            # Start polling
            LOGGER.info("Starting polling...")
            await self.bot.start()
            await self.bot.updater.start_polling(drop_pending_updates=True)
            
            # Start health check in background
            self.health_check_task = asyncio.create_task(
                self.health_check(start_time)
            )
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
        except Exception as e:
            LOGGER.error(f"Bot stopped due to error: {e}", exc_info=True)
        finally:
            await self.cleanup()

def setup_signal_handlers(bot_manager: BotManager):
    """Setup signal handlers for graceful shutdown"""
    loop = asyncio.get_running_loop()
    
    def signal_handler():
        LOGGER.info("Received shutdown signal")
        bot_manager.shutdown_event.set()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, signal_handler)

def run():
    """Run the bot."""
    try:
        LOGGER.info("Starting event loop...")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        bot_manager = BotManager()
        
        async def start_bot():
            # Set up signal handlers after loop is running
            setup_signal_handlers(bot_manager)
            await bot_manager.run()
        
        loop.run_until_complete(start_bot())
        
    except KeyboardInterrupt:
        LOGGER.info("Received keyboard interrupt")
    except Exception as e:
        LOGGER.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        LOGGER.info("Closing event loop...")
        # Ensure all tasks are completed or cancelled
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
        LOGGER.info("Event loop closed")
    
if __name__ == "__main__":
    run()